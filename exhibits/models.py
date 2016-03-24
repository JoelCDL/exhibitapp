from __future__ import unicode_literals

from django.contrib.auth.models import User
from django.db import models
from positions.fields import PositionField
from calisphere.cache_retry import SOLR_select, SOLR_raw, json_loads_url
from django.core.urlresolvers import reverse
from calisphere.views import getCollectionData, getRepositoryData

# only if you need to support python 2: 
from django.utils.encoding import python_2_unicode_compatible

RENDERING_OPTIONS = (
    ('H', 'HTML'),
    ('T', 'Plain Text'),
    ('M', 'Markdown')
)

@python_2_unicode_compatible    # only if you need to support python 2
class Exhibit(models.Model):
    title = models.CharField(max_length=512)
    slug = models.SlugField(max_length=255, unique=True)
    
    blockquote = models.CharField(max_length=512, blank=True)     #default for blockquote is first sentence of essay
    about_exhibit = models.TextField(blank=True)
    essay = models.TextField(verbose_name='Exhibit Overview', blank=True)
    render_as = models.CharField(max_length=1, choices=RENDERING_OPTIONS, default='H')
    publish = models.BooleanField(verbose_name='Ready for publication?', default=False)
    color = models.CharField(max_length=20, blank=True)
    
    scraped_from = models.CharField(max_length=250, blank=True)

    hero = models.ImageField(blank=True, verbose_name='Hero Image', upload_to='uploads/')

    meta_description = models.CharField(max_length=255, blank=True)
    meta_keywords = models.CharField(max_length=255, blank=True)
    
    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('exhibits:exhibitView', kwargs={'exhibit_id': self.id, 'exhibit_slug': self.slug})

@python_2_unicode_compatible    # only if you need to support python 2
class ExhibitItem(models.Model):
    item_id = models.CharField(max_length=200)
    exhibit = models.ForeignKey(Exhibit, on_delete=models.CASCADE)
    order = PositionField(collection='exhibit')
    essay = models.TextField(blank=True, verbose_name='Item-level exhibit information')
    render_as = models.CharField(max_length=1, choices=RENDERING_OPTIONS, default='T')
    
    #lat/long models
    lat = models.FloatField(default=37.8086906)
    lon = models.FloatField(default=-122.2675416)
    place = models.CharField(max_length=512, blank=True)
    exact = models.BooleanField(default=False)    
    def __str__(self):
        return self.item_id

    def solrData(self):
        item_id_search_term = 'id:"{0}"'.format(self.item_id)
        item_solr_search = SOLR_select(q=item_id_search_term)
        if len(item_solr_search.results) > 0:
            item = item_solr_search.results[0]

            item['parsed_collection_data'] = []
            item['parsed_repository_data'] = []
            for collection_data in item['collection_data']:
                item['parsed_collection_data'].append(getCollectionData(collection_data=collection_data))
            if 'repository_data' in item:
                for repository_data in item['repository_data']:
                    item['parsed_repository_data'].append(getRepositoryData(repository_data=repository_data))

            return item
        else:
            return None

@python_2_unicode_compatible
class NotesItem(models.Model):
    title = models.CharField(max_length=200)
    exhibit = models.ForeignKey(Exhibit, on_delete=models.CASCADE)
    order = PositionField(collection='exhibit')
    essay = models.TextField(blank=True, verbose_name='Note')
    render_as = models.CharField(max_length=1, choices=RENDERING_OPTIONS, default='T')
    
    def __str__(self):
        return self.title

@python_2_unicode_compatible
class HistoricalEssay(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=255, unique=True)
    blockquote = models.CharField(max_length=200, blank=True)
    essay = models.TextField(blank=True)
    render_as = models.CharField(max_length=1, choices=RENDERING_OPTIONS, default='H')
    
    about_essay = models.TextField(blank=True)
    go_further = models.TextField(blank=True)
    
    publish = models.BooleanField(verbose_name='Ready for publication?', default=False)
    meta_description = models.CharField(max_length=255, blank=True)
    meta_keywords = models.CharField(max_length=255, blank=True)
    
    def __str__(self):
        return self.title

class HistoricalEssayExhibit(models.Model):
    exhibit = models.ForeignKey(Exhibit, on_delete=models.CASCADE)
    historicalEssay = models.ForeignKey(HistoricalEssay, on_delete=models.CASCADE)
    order = PositionField(collection='exhibit')
    
    class Meta(object):
        unique_together = ('exhibit', 'historicalEssay')
        verbose_name = 'Historical Essay'

@python_2_unicode_compatible
class LessonPlan(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=255, unique=True)
    essay = models.TextField(blank=True, verbose_name='Lesson plan')
    render_as = models.CharField(max_length=1, choices=RENDERING_OPTIONS, default='H')
    
    publish = models.BooleanField(verbose_name='Ready for publication?', default=False)
    meta_description = models.CharField(max_length=255, blank=True)
    meta_keywords = models.CharField(max_length=255, blank=True)
    
    def __str__(self):
        return self.title

class LessonPlanExhibit(models.Model):
    exhibit = models.ForeignKey(Exhibit, on_delete=models.CASCADE)
    lessonPlan = models.ForeignKey(LessonPlan, on_delete=models.CASCADE)
    order = PositionField(collection='exhibit')
    
    class Meta(object):
        unique_together = ('exhibit', 'lessonPlan')
        verbose_name = 'Lesson Plan'

class Theme(models.Model): 
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=255, unique=True)
    color = models.CharField(max_length=20, blank=True)
    about_theme = models.TextField(blank=True)
    essay = models.TextField(blank=True, verbose_name='Theme overview')
    render_as = models.CharField(max_length=1, choices=RENDERING_OPTIONS, default='H')
    
    hero = models.ImageField(blank=True, verbose_name='Hero Image', upload_to='uploads/')

    publish = models.BooleanField(verbose_name='Ready for publication?', default=False)
    meta_description = models.CharField(max_length=255, blank=True)
    meta_keywords = models.CharField(max_length=255, blank=True)

    def get_absolute_url(self):
        return reverse('exhibits:themeView', kwargs={'theme_id': self.id, 'theme_slug': self.slug})

    def __str__(self):
        return self.title

class BrowseTermGroup(models.Model):
    group_title = models.CharField(max_length=200, blank=True)
    group_note = models.TextField(blank=True)
    render_as = models.CharField(max_length=1, choices=RENDERING_OPTIONS, default='H')
    theme = models.ForeignKey(Theme, on_delete=models.CASCADE)
    order = PositionField(collection='theme')

    def __str__(self):
        return self.group_title

    class Meta:
        ordering = ['order']

class BrowseTerm(models.Model):
    link_text = models.CharField(max_length=200)
    link_location = models.CharField(max_length=500)
    browse_term_group = models.ForeignKey(BrowseTermGroup, on_delete=models.CASCADE)
    order = PositionField(collection='browse_term_group')

    def __str__(self):
        return self.link_text

    class Meta:
        ordering = ['order']

# Exhibits ordered within Themes
class ExhibitTheme(models.Model):
    exhibit = models.ForeignKey(Exhibit, on_delete=models.CASCADE)
    theme = models.ForeignKey(Theme, on_delete=models.CASCADE)
    order = PositionField(collection='theme')

    class Meta(object):
        unique_together = ('exhibit', 'theme')
        verbose_name = 'Exhibit'

class LessonPlanTheme(models.Model):
    lessonPlan = models.ForeignKey(LessonPlan, on_delete=models.CASCADE)
    theme = models.ForeignKey(Theme, on_delete=models.CASCADE)
    order = PositionField(collection='theme')
    
    class Meta(object):
        unique_together = ('lessonPlan', 'theme')
        verbose_name = 'Lesson Plan'

class HistoricalEssayTheme(models.Model):
    historicalEssay = models.ForeignKey(HistoricalEssay, on_delete=models.CASCADE)
    theme = models.ForeignKey(Theme, on_delete=models.CASCADE)
    order = PositionField(collection='theme')
    
    class Meta(object):
        unique_together = ('historicalEssay', 'theme')
        verbose_name = 'Historical Essay'