from django.conf.urls import patterns, include, url
from django.contrib import admin
from django.http import HttpResponse
from django.views.generic import TemplateView

from calisphere.contact_form_view import CalisphereContactFormView

admin.autodiscover()

urlpatterns = patterns('',
    url(r'^', include('calisphere.urls', namespace="calisphere")),
    url(r'^admin/', include(admin.site.urls)),
    url(r'^contact/$',
        CalisphereContactFormView.as_view(),
        name='contact_form'),
    url(r'^contact/sent/$',
        TemplateView.as_view(
            template_name='contact_form/contact_form_sent.html'),
        name='contact_form_sent'),
    url(r'^robots.txt$',
        lambda r: HttpResponse("User-agent: *\nDisallow: /", content_type="text/plain")
    )
)
