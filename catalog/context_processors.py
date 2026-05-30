import random
from random import Random
from datetime import date
from catalog.models import Category

def global_categories(request):

    categories = list(
        Category.objects.filter(parent=None)
    )
    second_categories = list(
        Category.objects.filter(parent=None)
    )

    # shuffle the navigations DAILY
    rnd = Random(date.today().toordinal())
    rnd.shuffle(categories)

    # shuffle the second navigations on every request
    random.shuffle(second_categories)

    return {
        "nav_categories": categories[:4],
        "second_categories":second_categories[:4]
    }


