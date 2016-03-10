from django.shortcuts import get_object_or_404, render
from django.http import HttpResponse
from exhibits.models import *
from calisphere.cache_retry import SOLR_select, SOLR_raw, json_loads_url

def exhibitDirectory(request):
    return HttpResponse("Hello, world. You're at the exhibit index.")

def exhibitView(request, exhibit_id, exhibit_slug):
    exhibit = get_object_or_404(Exhibit, pk=exhibit_id)
    exhibitItems = exhibit.exhibititem_set.all().order_by('order')

    itemQuery = ''
    for exhibitItem in exhibitItems:
        itemQuery = itemQuery + exhibitItem.item_id + " OR "

    itemQuery = itemQuery[0:-4]

    # item_solr_search = SOLR_select(q=itemQuery)
    #
    # for result in item_solr_search.results:
    #     exhibitItem = exhibitItems.get(item_id=result['id'])

    return render(request, 'exhibits/exhibitView.html', {'exhibit': exhibit, 'q': '', 'solrExhibitItems': item_solr_search.results})

# def exhibitItemView(request, item_id=''):
#     item_id_search_term = 'id:"{0}"'.format(item_id)
#     item_solr_search = SOLR_select(q=item_id_search_term)
#     if not item_solr_search.numFound:
#         # second level search
#         def _fixid(id):
#             return re.sub(r'^(\d*--http:/)(?!/)', r'\1/', id)
#         old_id_search = SOLR_select(q='harvest_id_s:{}'.format(_fixid(item_id)))
#         if old_id_search.numFound:
#             return redirect('calisphere:itemView', old_id_search.results[0]['id'])
#         else:
#             raise Http404("{0} does not exist".format(item_id))
#     for item in item_solr_search.results:
#         if 'structmap_url' in item and len(item['structmap_url']) >= 1:
#             item['harvest_type'] = 'hosted'
#             structmap_url = string.replace(item['structmap_url'], 's3://static', 'https://s3.amazonaws.com/static');
#             structmap_data = json_loads_url(structmap_url)
#
#             if 'structMap' in structmap_data:
#                 # complex object
#                 # if parent content file, get it
#                 if 'format' in structmap_data and structmap_data['format'] != 'file':
#                     item['contentFile'] = getHostedContentFile(structmap_data)
#                 # otherwise get first component file
#                 else:
#                     component = structmap_data['structMap'][0]
#                     item['contentFile'] = getHostedContentFile(component)
#             else:
#                 # simple object
#                 if 'format' in structmap_data:
#                     item['contentFile'] = getHostedContentFile(structmap_data)
#         else:
#             item['harvest_type'] = 'harvested'
#             if 'url_item' in item:
#                 if item['url_item'].startswith('http://ark.cdlib.org/ark:'):
#                     item['oac'] = True
#                     item['url_item'] = string.replace(item['url_item'], 'http://ark.cdlib.org/ark:', 'http://oac.cdlib.org/ark:')
#                     item['url_item'] = item['url_item'] + '/?brand=oac4'
#                 else:
#                     item['oac'] = False
#             #TODO: error handling 'else'
#
#         item['parsed_collection_data'] = []
#         item['parsed_repository_data'] = []
#         item['institution_contact'] = []
#         for collection_data in item['collection_data']:
#             item['parsed_collection_data'].append(getCollectionData(collection_data=collection_data))
#         if 'repository_data' in item:
#             for repository_data in item['repository_data']:
#                 item['parsed_repository_data'].append(getRepositoryData(repository_data=repository_data))
#
#                 institution_url = item['parsed_repository_data'][0]['url']
#                 institution_details = json_loads_url(institution_url + "?format=json")
#                 if 'ark' in institution_details and institution_details['ark'] != '':
#                     contact_information = json_loads_url("http://dsc.cdlib.org/institution-json/" + institution_details['ark'])
#                 else:
#                     contact_information = ''
#
#                 item['institution_contact'].append(contact_information)
#
#     meta_image = False
#     if item_solr_search.results[0].get('reference_image_md5', False):
#         meta_image = urlparse.urljoin(
#             settings.UCLDC_FRONT,
#             u'/crop/999x999/{0}'.format(item_solr_search.results[0]['reference_image_md5']),
#         )
#
#     return render (request, 'calisphere/itemViewer.html', {
#         'q': '',
#         'item': item_solr_search.results[0],
#         'item_solr_search': item_solr_search,
#         'meta_image': meta_image,
#     })
#
