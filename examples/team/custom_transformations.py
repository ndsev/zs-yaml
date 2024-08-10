from datetime import datetime


def calculate_age(transformer, birthdate):
    born = datetime.strptime(birthdate, "%Y-%m-%d")
    today = datetime.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))
