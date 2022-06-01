# Diablo 2 - Lord of Destruction 1.13d

treasure_classes.py is script for calculation of probabilities from fixed treasure class and level (monster level or level of chest). It outputs (classid, quality, probability) entries. How to convert classid numbers into actual item name? How to find out level and treasure class index of monster? Refer to other Diablo 2 related resources. Including hardcoded conversion tables was silly, and implementing it in *good* way is a bit tedious. Determination of treasure class by monster is complicated topic.

### Item qualities

1. low quality
2. normal quality
3. high quality
4. magic
5. set
6. rare
7. unique

The game first decide what base item it drops. Then it picks quality. And after quality is decided, it checks can it spawn an item. This calculator **ignores availability** of unique and set items. When unique is not available for chosen base item the game will reroll rare item with increased durability, if this item doesn't allow to be rare, it will reroll magic item. So, for cases when unique item is not available you may think of unique probability to be a probability to roll rare item with increased durability. Similarly, when set item is not available for chosen base item the game will reroll magic item with increased durability. So in this case you may also think of it as a probability of magic item with increased durability.

### Probability

To be clear, what is calculated actually is not a probability. Correct math term for that is **expected value**. Expected value of what? Expected value of number of items like that. For example, if you'll do 1000 runs on Mephisto and count **all** items dropped from him the average number of items will be as calculated from this calculator. The more runs you do the closer the average will be to the calculated one.

## Methodology

The game was modified to perform multiple drops from single treasure class at once. And, while doing multiple drops it also was logging all (classid, quality) pairs with some additional debug information. Drop algorithm was analyzed and partially reimplemented to match results from the game. Logs from the game was done with one million of drops. Then, custom implementation was simulating 10 billions of drops.

The thing you'll get with this kind of process is approximation of average. Each time you do this, you get some number which is close but different. Suppose you get difference less than 0.0001 with the calculated average? How can you tell is the calculation correct or not? Well, the average of 10 billion of drops is the so called *random variable*. And it has distribution. To make sure the calculator is correct we want to tell is this possible for the average we get from the game to be from the distribution we calculated. It's well known that deviation is reduced by number of *samples* of value. If the number of samples is increased in 100 times then deviation is reduced in 10 times. In other words, increase of the samples in N times the deviation reduce in square root of N. In theory, 10 billions of *samples* should have deviation reduced in 100 000 times from initial. For expansion hell countess worst difference between the calculated value and the average from the game is close to 0.00001, but we don't know its original deviation. When I reduced number of samples in 100 times I got worst difference approximately 0.00007. Which is close to 10 times worse. So, looks plausible.
