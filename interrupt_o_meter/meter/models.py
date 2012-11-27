from django.db import models

# Create your models here.

class DataPoint(models.Model):
    name = models.CharField(max_length=255)
    value = models.IntegerField()

class DataPointDate(models.Model):
    name = models.CharField(max_length=255)
    value = models.DateTimeField()

class DataDump(models.Model):
    date = models.DateTimeField()
    content = models.TextField()
