import argparse
import struct
import math
from fractions import Fraction

def get_item_txt(idx):
	if idx < 0 or idx >= len(items_txt):
		raise Exception(f'no item_txt for classid {idx}')
	return items_txt[idx]

def get_itemtype_txt(idx):
	if idx < 0 or idx >= len(itemtypes_txt):
		raise Exception(f'no itemtype_txt for type {idx}')
	return itemtypes_txt[idx]

def item_has_type(classid, type_id):
	if type_id < 0 or type_id >= len(itemtypes_txt):
		raise Exception(f'item_has_type wrong type_id {type_id}')
	txt = get_item_txt(classid)
	item_type = struct.unpack('<h', txt[0x11E:0x11E+2])[0]
	was = [False] * len(itemtypes_txt)
	q = [item_type]
	while q:
		idx = q.pop()
		if was[idx]:
			continue
		if idx == type_id:
			return True
		was[idx] = True
		type = get_itemtype_txt(idx)
		Equiv1, Equiv2 = struct.unpack('<hh', type[4:8])
		q.append(Equiv1)
		q.append(Equiv2)
	return False

def get_quality_chance(difference, magic_bonus, coef, base, divisor, minimum, bonus):
	v = (base - int(difference / divisor)) * 128
	if magic_bonus != 0:
		if magic_bonus > 10:
			tmp = int((magic_bonus * coef) / (coef + magic_bonus))
		else:
			tmp = magic_bonus
		if tmp != -100:
			v = int((v * 100) / (tmp + 100))
	v = max(v, minimum)
	return v - int(v * bonus / 1024)

def get_itemratio_txt(class_specific, uber, version):
	if version != 0 and version != 100:
		raise Exception(f'wrong version {version}')
	best_ver = -1
	best_idx = -1
	for i in range(len(itemratio_txt)):
		if (itemratio_txt[i]['ClassSpecific'] == class_specific
		and itemratio_txt[i]['Uber'] == uber
		and itemratio_txt[i]['Version'] <= version
		and itemratio_txt[i]['Version'] >= best_ver):
			best_ver = itemratio_txt[i]['Version']
			best_idx = i
	if best_idx < 0:
		raise Exception(f'failed to find itemratio {class_specific} {uber}')
	return itemratio_txt[best_idx]

def quality_probability(classid, monster_level, magic_bonus, bonus):
	txt = get_item_txt(classid)
	item_type = struct.unpack('<h', txt[0x11E:0x11E+2])[0]
	type_txt = get_itemtype_txt(item_type)
	res = [0] * 9
	if type_txt[0x16]: # normal
		res[2] = 1
		return res
	if txt[0x129]: # unique
		res[7] = 1
		return res
	if type_txt[0x14] and txt[0x12A]: # magic & quest
		res[7] = 1
		return res
	# appropriate itemratio_txt settings
	class_specific = int(type_txt[0x21] - 7 < 0)
	uber = 0
	# is armor or weapon
	if item_has_type(classid, 0x32) or item_has_type(classid, 0x2D):
		code = txt[0x80:0x84]
		# ubercode and ultracode
		if code == txt[0x88:0x8C] or code == txt[0x8C:0x90]:
			if item_type != 0x26: # missilepotion
				uber = int(txt[0x12A] == 0) # quest
	ratio = get_itemratio_txt(class_specific, uber, 100)
	# actual quality determination
	ilvl = txt[0xFD]
	lvl_diff = monster_level - ilvl
	rem = 1
	if magic_bonus > -100:
		v = get_quality_chance(lvl_diff, magic_bonus, 250,
			ratio['Unique'], ratio['UniqueDivisor'], ratio['UniqueMin'], bonus['unique'])
		if v <= 128:
			res[7] = 1
			return res
		res[7] = Fraction(128, v) * rem
		rem *= (1 - Fraction(128, v))
		v = get_quality_chance(lvl_diff, magic_bonus, 500,
			ratio['Set'], ratio['SetDivisor'], ratio['SetMin'], bonus['set'])
		if v <= 128:
			res[5] = rem
			return res
		res[5] = Fraction(128, v) * rem
		rem *= (1 - Fraction(128, v))
		if type_txt[0x15] != 0: # rare
			v = get_quality_chance(lvl_diff, magic_bonus, 600,
				ratio['Rare'], ratio['RareDivisor'], ratio['RareMin'], bonus['rare'])
			if v <= 128:
				res[6] = rem
				return res
			res[6] = Fraction(128, v) * rem
			rem *= (1 - Fraction(128, v))
		if type_txt[0x14] != 0: # magic
			res[4] = rem
			return res
		v = (ratio['Magic'] - int(lvl_diff / ratio['MagicDivisor'])) * 128
		if magic_bonus != 0:
			v = int((v * 100) / (magic_bonus + 100))
		v = max(v, ratio['MagicMin'])
		v = v - int(v * bonus['magic'] / 1024)
		if v <= 128:
			res[4] = rem
			return res
		res[4] = Fraction(128, v) * rem
		rem *= (1 - Fraction(128, v))
	v = (ratio['HiQuality'] - int(lvl_diff / ratio['HiQualityDivisor'])) * 128
	if v <= 128:
		res[3] = rem
		return res
	res[3] = Fraction(128, v) * rem
	rem *= (1 - Fraction(128, v))
	v = (ratio['Normal'] - int(lvl_diff / ratio['NormalDivisor'])) * 128
	if v <= 128:
		res[2] = rem
		return res
	res[2] = Fraction(128, v) * rem
	res[1] = rem * (1 - Fraction(128, v))
	return res

def init():
	global L, TC, items_txt, itemtypes_txt, itemratio_txt

	with open('treasure_classes.dump', 'r') as f:
		offset, TC_cnt = (int(i, 16) for i in f.readline().split())
		TC = [None] * TC_cnt
		for i in range(TC_cnt):
			b = bytes.fromhex(f.readline())
			vals = struct.unpack('<HHiiiiihhhhhhhhI', b)
			d = dict()
			for j, v in enumerate(('group level count classic expansion nPick noDrop unk1'
				+ ' magic rare set unique TC30 TC32 unk2 list_addr').split()):
				d[v] = vals[j]
			TC[i] = d
		L = dict()
		while True:
			s = f.readline().strip()
			if s == '':
				break
			addr, val = s.split()
			L[int(addr, 16)] = struct.unpack('<iihhh'+'hhhhhh', bytes.fromhex(val)[:4*2+2*3+2*6])
		for i in range(TC_cnt):
			TC[i]['list'] = [L[TC[i]['list_addr'] + j * 0x1C] for j in range(TC[i]['count'])]


	items_txt = []
	for fname in 'weapons', 'armor', 'misc':
		with open(fname + '.bin', 'rb') as f:
			count = struct.unpack('<i', f.read(4))[0]
			s = f.read()
		if count * 0x1A8 != len(s):
			raise Exception(f'{count*0x1A8} != {len(s)}')
		for i in range(0, len(s), 0x1A8):
			items_txt.append(s[i:i+0x1A8])
	#print('items_txt:', len(items_txt))

	itemtypes_txt = []
	with open('itemtypes.bin', 'rb') as f:
		count = struct.unpack('<i', f.read(4))[0]
		s = f.read()
	if count * 0xE4 != len(s):
		raise Exception(f'{count*0xE4} != {len(s)}')
	for i in range(0, len(s), 0xE4):
		itemtypes_txt.append(s[i:i+0xE4])
	#print('itemtypes_txt:', len(itemtypes_txt))

	itemratio_txt = []
	with open('itemratio.bin', 'rb') as f:
		count = struct.unpack('<i', f.read(4))[0]
		s = f.read()
	if count * 0x44 != len(s):
		raise Exception(f'{count*0xE4} != {len(s)}')
	for i in range(0, len(s), 0x44):
		vals = struct.unpack('<'+'i'*16+'hbb', s[i:i+0x44])
		d = dict()
		for j, name in enumerate(
			('Unique UniqueDivisor UniqueMin'
			+ ' Rare RareDivisor RareMin'
			+ ' Set SetDivisor SetMin'
			+ ' Magic MagicDivisor MagicMin'
			+ ' HiQuality HiQualityDivisor'
			+ ' Normal NormalDivisor'
			+ ' Version Uber ClassSpecific').split()):
			d[name] = vals[j]
		itemratio_txt.append(d)
	#print('itemratio_txt:', len(itemratio_txt))

def dcoef(p1, p2, picks1, picks2, a, cap):
	r = 0
	r1 = 0
	for i in range(picks1):
		for j in range(i + 1):
			total = (i - j) * picks2
			for k in range(total + 1):
				if k + j > cap - 1:
					break
				tmp = (p2**j)*(p1**(i-j))*(math.factorial(i)//math.factorial(j)//math.factorial(i-j))
				tmp *= ((1 - a)**k)*(a**(total-k))*(math.factorial(total)//math.factorial(k)//math.factorial(total-k))
				tmp1 = 0
				for z in range(min(picks2 + 1, cap - j - k)):
					for zz in range(z, picks2):
						tmp1 += ((1-a)**z)*(a**(zz-z))*(math.factorial(zz)//math.factorial(z)//math.factorial(zz-z))
				r += tmp*tmp1
				r1 += tmp
	return Fraction(r, picks1*picks2), Fraction(r, picks1*picks2), p2*r1-Fraction(p2*picks1*r, picks1*picks2)

class calculator:
	def __init__(self, monster_level, magic_bonus, expansion, players_mod, find_item):
		self.monster_level = monster_level
		self.magic_bonus = magic_bonus
		self.expansion = expansion
		self.players_mod = players_mod
		self.find_item = find_item
		self.cache = dict()
		self.cache1 = dict()

	def get(self, tc, picks, bonus):
		T = TC[tc]
		key_tuple = (tc, picks, tuple(sorted(bonus.items())))
		res = self.cache.get(key_tuple)
		if res is not None:
			return res
		ver = T['expansion' if self.expansion else 'classic']
		count = T['count']
		if ver == 0 or count <= 0:
			return {None: 1, 'max': 0}
		noDropP = 0
		if T['nPick'] >= 0:
			noDrop = T['noDrop']
			if noDrop > 0 and self.players_mod > 1:
				noDrop = int(ver/((noDrop/(noDrop + ver))**(-self.players_mod)-1))
			if self.find_item:
				var = (0, ver)
			else:
				var = (-noDrop, ver)
				noDropP = Fraction(noDrop, (ver + noDrop))
		else:
			var = (-T['nPick'] - picks, -T['nPick'] - picks + 1)
			if var[0] >= ver:
				noDropP = 1
		idxp = [0] * count
		l = T['list']
		repeat = 0
		var_len = var[1] - var[0]
		if self.expansion:
			for j in range(count):
				v = l[j+1][1] if j + 1 < count else ver
				v = min(v, var[1]) - max(l[j][1], var[0])
				if v >= 0:
					idxp[j] += Fraction(v, var_len)
		else:
			for j in range(count):
				if (l[j][4] & 0x10) == 0:
					i = j + 1
					while i < count and (l[i][4] & 0x10) != 0:
						i += 1
					v = l[i][0] if i < count else ver
					v = min(v, var[1]) - max(l[j][0], var[0])
					if v >= 0:
						idxp[j] += Fraction(v, var_len)
		res = {None: 0, 'max': 0}
		tmp = []
		for idx in range(count):
			p = idxp[idx]
			if p == 0:
				continue
			entry = l[idx]
			if (entry[4] & 4) != 0: # other TC
				tc1 = entry[2]
				T1 = TC[tc1]
				picks1 = max(abs(T1['nPick']), 1)
				bonus1 = dict()
				for i in 'magic rare set unique TC30 TC32'.split():
					bonus1[i] = max(bonus[i], T1[i])
				res1 = self.get(tc1, picks1, bonus1)
				for i, d1 in res1.items():
					if i is None:
						noDropP += d1 * p
					elif i == 'max':
						res['max'] = max(res['max'], d1)
					else:
						if i not in res:
							res[i] = dict()
						d = res[i]
						for j, p1 in d1.items():
							d[j] = d.get(j, 0) + p1 * p
			else:
				classid = entry[2]
				if classid != -1:
					if not self.expansion:
						txt = get_item_txt(classid)
						if struct.unpack('<h', txt[0xF6:0xF8])[0] >= 100:
							noDropP += p
							continue # just skip
						bonus1 = dict()
						for i, k in enumerate('magic rare set unique TC30 TC32'.split()):
							bonus1[k] = max(bonus[k], entry[i + 5])
					else:
						bonus1 = bonus
					quality2 = 0
					if (entry[4] & 1) != 0:
						quality2 = entry[3] + 1
						quality = 7
					elif (entry[4] & 2) != 0:
						quality2 = entry[3] + 1
						quality = 5
					#elif item_quality == 0:
					#	quality = calculate_quality(classid, monster_level, magic_bonus, bonus)
					#else:
					#	quality = item_quality
					else:
						quality = 0
					flags = 0
					if T['TC30'] > 0:
						raise Exception('TODO') # never happens
					if T['TC32'] > 0:
						raise Exception('TODO') # never happens
					if not self.expansion:
						txt = get_item_txt(classid)
						item_type = struct.unpack('<h', txt[0x11E:0x11E+2])[0]
						if get_itemtype_txt(item_type)[0x10] != 0: # throwable
							repeat += p
							continue
					# drop
					#item = (classid, quality, quality2, flags)
					# if item_has_type(gold)
					#   increase gold times (entry[3]/256)
					dd = (quality, tuple(sorted(bonus1.items())))
					if classid not in res:
						res[classid] = dict()
					res[classid][dd] = res[classid].get(dd, 0) + p
					res['max'] = max(res['max'], 1)
					# if item_has_type(gold)
					#   apply find gold bonus from attacker'''
		res[None] += noDropP
		if repeat != 0:
			total = var_len
			for i, d in res.items():
				if i is not None and i != 'max':
					for j in d:
						d[j] *= Fraction(1, 1 - repeat)
			res[None] *= Fraction(1, 1 - repeat)
		if picks > 1:
			if T['nPick'] >= 0:
				for i, d in res.items():
					if i is not None and i != 'max':
						for j in d:
							d[j] *= picks
				res[None] **= picks
				res['max'] *= picks
			else:
				res2 = self.get(tc, picks - 1, bonus)
				for i, d in res2.items():
					if i is not None and i != 'max':
						for j, p1 in d.items():
							if i not in res:
								res[i] = dict()
							res[i][j] = res[i].get(j, 0) + p1
				res['max'] += res2['max']
				res[None] *= res2[None]
		self.cache[key_tuple] = res
		return res

	def get_capped(self, tc, picks, bonus):
		key_tuple = (tc, picks, tuple(sorted(bonus.items())))
		res = self.cache1.get(key_tuple)
		if res is not None:
			return res
		if tc >= 989 and tc <= 994:
			bonus = dict()
			tc_sub = TC[tc]['list'][1][2]
			for z in 'magic rare set unique TC30 TC32'.split():
				bonus[z] = TC[tc_sub][z]
			ddd = dcoef(Fraction(2, 3), Fraction(1, 3), 5, 7, self.get(tc_sub, 1, bonus)[None], 6)
			res = dict()
			for classid, d in self.get(tc, picks, bonus).items():
				if classid is None:
					res[None] = d
				elif classid == 'max':
					res[classid] = max(d, 6)
				else:
					res[classid] = dict()
					if classid == 529:
						for k, p in d.items():
							res[classid][k] = p * ddd[1] + ddd[2]
					else:
						for k, p in d.items():
							res[classid][k] = p * ddd[0]
		elif tc >= 1004 and tc <= 1006:
			tc_sub1 = TC[tc]['list'][0][2]
			tc_sub2 = TC[tc]['list'][1][2]
			noDrop1 = self.get(tc_sub1, 1, bonus)[None]
			noDrop2 = self.get(tc_sub2, 1, bonus)[None]
			res2 = self.get(tc_sub2, max(abs(TC[tc_sub2]['nPick']), 1), bonus)
			res = dict()
			for classid, d in self.get(tc, picks, bonus).items():
				if classid is None:
					res[None] = d
				elif classid == 'max':
					res[classid] = max(d, 6)
				else:
					res[classid] = d.copy()
					if classid in res2:
						for k, p in res2[classid].items():
							res[classid][k] = res[classid].get(k, 0) - p*(1-noDrop1)**4*((1-noDrop1)*(2+noDrop2)*(1-noDrop2)+5*noDrop1*(1-noDrop2)**2)/3
		elif TC[tc]['nPick'] == 7:
			res = dict()
			r = Fraction((7 - (1 - self.get(tc, 1, bonus)[None])**6), 7)
			for classid, d in self.get(tc, picks, bonus).items():
				if classid is None:
					res[classid] = d
				elif classid == 'max':
					res[classid] = min(d, 6)
				else:
					res[classid] = dict()
					for k, p in d.items():
						res[classid][k] = p * r
		else:
			res = self.get(tc, picks, bonus)
		self.cache1[key_tuple] = res
		return res

	def solve(self, tc, classid):
		T = TC[tc]
		bonus = dict()
		for i in 'magic rare set unique TC30 TC32'.split():
			bonus[i] = T[i]
		results = self.get_capped(tc, max(abs(T['nPick']), 1), bonus)
		results = results.get(classid)
		result = [0]*8
		if results is None:
			return result
		for i, p in results.items():
			quality = i[0]
			if quality == 0:
				bonus = dict(i[1])
				prob = quality_probability(classid, self.monster_level, self.magic_bonus, bonus)
				for quality in range(8):
					result[quality] += prob[quality] * p
			elif quality > 0:
				result[quality] += p
		return result

# 834 37 classic nm andariel
# 446 35 classic nm dark one
# 991 88 expansion hell duriel
# 850 87 expansion hell mephisto

def main():
	parser = argparse.ArgumentParser(description='output (classid, quality, probability) tuples for fixed treasure class and level ignoring availability of unique and set items')
	parser.add_argument('tc', type=int, help='treasure class index')
	parser.add_argument('monlvl', type=int, help='for monsters it\'s level of monster, for chests it\'s often 1 or 2, hard to tell')
	parser.add_argument('--magicbonus', '-mf', help='item magic find bonus', default=0, type=int)
	parser.add_argument('--players_mod', '-p', help='it is calculated by floor((players_in_game + players_in_party) / 2)', default=1, type=int)
	parser.add_argument('--lod', '--expansion', dest='expansion', action='store_true', default=True)
	parser.add_argument('--classic', dest='expansion', action='store_false')
	parser.add_argument('--find', '-f', help='item find skill', action='store_true')
	parser.add_argument('--fractions', '-F', help='output probabilities as fractions', action='store_true', default=False)
	args = parser.parse_args()
	print(args)
	init()

	s = calculator(args.monlvl, args.magicbonus, args.expansion, args.players_mod, args.find)
	for classid in range(len(items_txt)):
		results = s.solve(args.tc, classid)
		v = sum(results)
		if v != 0:
			print(classid, 'all', v if args.fractions else float(v))
		for quality in range(8):
			if results[quality] != 0:
				print(classid, quality, results[quality] if args.fractions else float(results[quality]))

if __name__ == '__main__':
	main()
