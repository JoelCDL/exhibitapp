from django.shortcuts import render
from django.http import HttpResponse
from django import forms
from django.conf import settings
from django.core.urlresolvers import reverse
from django.core.cache import cache
from django.http import Http404
from calisphere.collection_data import CollectionManager
from collections import namedtuple

import md5s3stash
import operator
import math
import solr
import re
import urllib2
import copy
import simplejson as json
from retrying import retry
import pickle
import hashlib
import string

FACET_TYPES = [('type_ss', 'Type of Object'), ('repository_data', 'Institution Owner'), ('collection_data', 'Collection')]

def get_campus_list():
    campus_list = json.loads(urllib2.urlopen("https://registry.cdlib.org/api/v1/campus/?format=json").read())
    campus_list = sorted(list(campus_list['objects']), key=lambda campus: (campus['position']))
    campuses = []
    for campus in campus_list:
        campus_id = campus['resource_uri'].split('/')[-2]
        campuses.append({'name': campus['name'], 'slug': campus['slug'], 'id': campus_id})

    return campuses

CAMPUS_LIST = get_campus_list()

SOLR = solr.SearchHandler(
    solr.Solr(
        settings.SOLR_URL,
        post_headers = {
          'X-Authentication-Token': settings.SOLR_API_KEY,
        },
    ),
    "/query"
)

class SolrCache(object):
    pass

def kwargs_md5(**kwargs):
    m = hashlib.md5()
    m.update(pickle.dumps(kwargs))
    return m.hexdigest()

@retry(stop_max_delay=3000)  # milliseconds
def SOLR_select(**kwargs):
    # look in the cache
    key = kwargs_md5(**kwargs)
    sc = cache.get(key)
    if not sc:
        # do the solr look up
        sr = SOLR(**kwargs)
        # copy attributes that can be pickled to new object
        sc = SolrCache()
        sc.results = sr.results
        sc.header = sr.header
        sc.facet_counts = getattr(sr, 'facet_counts', None)
        sc.numFound = sr.numFound
        cache.set(key, sc, 60*15)  # seconds
    return sc

# [bt: is this still really used?]
def process_media(item):
    if 'reference_image_md5' in item:
        item['reference_image_http'] = settings.THUMBNAIL_URL + 'clip/178x100/' + item['reference_image_md5']
    elif 'url_item' in item:
        item['reference_image_http'] = "http://www.calisphere.universityofcalifornia.edu/images/misc/no_image1.gif"
    else:
        item['reference_image_http'] = ""

    item['href'] = '/itemView/{0}/'.format( item['id'] )

# concat query with 'AND'
def concat_query(q, rq):
    if q == '': return rq
    elif rq == '': return q
    else: return q + ' AND ' + rq

# concat filters with 'OR'
def concat_filters(filters, filter_type):
    # OR-ING FILTERS OF ONE TYPE, YET AND-ING FILTERS OF DIFF TYPES
    fq_contents = filter_type + ': '

    for counter, f in enumerate(filters):
        fq_contents = fq_contents + '"' + f + '"'
        # if not at the last filter term, continue OR-ing together terms
        if counter < len(filters)-1:
            fq_contents = fq_contents + " OR " + filter_type + ': '

    return [fq_contents]

# collect filters into an array
def solrize_filters(filters):
    fq = []
    for filter_type in FACET_TYPES:
        if len(filters[filter_type[0]]) > 0:
            fq.extend(concat_filters(filters[filter_type[0]], filter_type[0]))

    return fq

def process_facets(facets, filters):
    display_facets = dict((facet, count) for facet, count in facets.iteritems() if count != 0)
    display_facets = sorted(display_facets.iteritems(), key=operator.itemgetter(1), reverse=True)

    for f in filters:
        if not any(f in facet for facet in display_facets):
            display_facets.append((f, 0))

    return display_facets

def getCollectionData(collection_data=None, collection_id=None):
    collection = {}
    if collection_data:
        collection['url'] = collection_data.split('::')[0] if len(collection_data.split('::')) >= 1 else ''
        collection['name'] = collection_data.split('::')[1] if len(collection_data.split('::')) >= 2 else ''

        collection_api_url = re.match(r'^https://registry\.cdlib\.org/api/v1/collection/(?P<url>\d*)/?', collection['url'])
        if collection_api_url is None:
            print 'no collection api url:'
            print collection_data
            collection['id'] = ''
        else:
            collection['id'] = collection_api_url.group('url')
    elif collection_id:
        collection['url'] = "https://registry.cdlib.org/api/v1/collection/{0}/".format(collection_id)
        collection['id'] = collection_id

        collection_details = json.loads(urllib2.urlopen(collection['url'] + "?format=json").read())
        collection['name'] = collection_details['name']
    return collection

def getCollectionMosaic(collection_url):
    collection_details = json.loads(urllib2.urlopen(collection_url + "?format=json").read())

    collection_repositories = []
    for repository in collection_details['repository']:
        if 'campus' in repository and len(repository['campus']) > 0:
            collection_repositories.append(repository['name'] + " - " + repository['campus'][0]['name'])
        else:
            collection_repositories.append(repository['name'])

    collection_api_url = re.match(r'^https://registry\.cdlib\.org/api/v1/collection/(?P<url>\d*)/?', collection_url)
    collection_id = collection_api_url.group('url')

    display_items = SOLR_select(
        q='*:*',
        fields='reference_image_md5, url_item, id, title, collection_url',
        rows=6,
        start=0,
        fq=['collection_url: \"' + collection_url + '\"']
    )

    for item in display_items.results:
        process_media(item)

    return {
        'name': collection_details['name'],
        'institutions': collection_repositories,
        'description': collection_details['description'],
        'collection_id': collection_id,
        'numFound': display_items.numFound,
        'display_items': display_items.results
    }

def getRepositoryData(repository_data=None, repository_id=None):
    repository = {}
    if repository_data:
        repository['url'] = repository_data.split('::')[0] if len(repository_data.split('::')) >= 1 else ''
        repository['name'] = repository_data.split('::')[1] if len(repository_data.split('::')) >= 2 else ''
        repository['campus'] = repository_data.split('::')[2] if len(repository_data.split('::')) >= 3 else ''

        repository_api_url = re.match(r'^https://registry\.cdlib\.org/api/v1/repository/(?P<url>\d*)/', repository['url'])
        if repository_api_url is None:
            print 'no repository api url'
            repository['id'] = ''
        else:
            repository['id'] = repository_api_url.group('url')
    elif repository_id:
        repository['url'] = "https://registry.cdlib.org/api/v1/repository/" + repository_id + "/"
        repository['id'] = repository_id

        repository_details = json.loads(urllib2.urlopen(repository['url'] + "?format=json").read())
        repository['name'] = repository_details['name']
        if repository_details['campus']:
            repository['campus'] = repository_details['campus'][0]['name']
        else:
            repository['campus'] = ''
    return repository

def facetQuery(facet_fields, queryParams, solr_search):
    facets = {}
    for facet_type in facet_fields:
        if facet_type in queryParams['filters'] and len(queryParams['filters'][facet_type]) > 0:
            # other_filters is all the filters except the ones of the current filter type
            other_filters = {key: value for key, value in queryParams['filters'].items()
                if key != facet_type}
            other_filters[facet_type] = []

            # perform the exact same search, but as though no filters of this type have been selected
            # to obtain the counts for facets for this facet type
            facet_solr_search = SOLR_select(
                q=queryParams['query_terms'],
                rows='0',
                fq=solrize_filters(other_filters),
                facet='true',
                facet_limit='-1',
                facet_field=[facet_type]
            )

            facets[facet_type] = process_facets(
                facet_solr_search.facet_counts['facet_fields'][facet_type],
                queryParams['filters'][facet_type]
            )
        else:
            facets[facet_type] = process_facets(
                solr_search.facet_counts['facet_fields'][facet_type],
                queryParams['filters'][facet_type] if facet_type in queryParams['filters'] else []
            )

    return facets

def processQueryRequest(request):
    # concatenate query terms from refine query and query box, set defaults
    q = request.GET['q'] if 'q' in request.GET else ''
    rq = request.GET.getlist('rq')
    query_terms = reduce(concat_query, request.GET.getlist('q') + request.GET.getlist('rq')) if 'q' in request.GET else ''
    rows = request.GET['rows'] if 'rows' in request.GET else '16'
    start = request.GET['start'] if 'start' in request.GET else '0'
    view_format = request.GET['view_format'] if 'view_format' in request.GET else 'thumbnails'
    rc_page = int(request.GET['rc_page']) if 'rc_page' in request.GET else 0

    # for each filter_type tuple ('solr_name', 'Display Name') in the list FACET_TYPES
    # create a dictionary with key solr_name of filter and value list of parameters for that filter
    # {'type': ['image', 'audio'], 'repository_name': [...]}
    filters = dict((filter_type[0], request.GET.getlist(filter_type[0])) for filter_type in FACET_TYPES)

    # use collection_id and repository_id to retrieve collection_data and repository_data filter values
    for i, filter_item in enumerate(filters['collection_data']):
        collection = getCollectionData(collection_id=filter_item)
        filters['collection_data'][i] = collection['url'] + "::" + collection['name']
    for i, filter_item in enumerate(filters['repository_data']):
        repository = getRepositoryData(repository_id=filter_item)
        filters['repository_data'][i] = repository['url'] + "::" + repository['name']
        if repository['campus'] != '':
            filters['repository_data'][i] = filters['repository_data'][i] + "::" + repository['campus']

    return {
        'q': q,
        'rq': rq,
        'query_terms': query_terms,
        'rows': rows,
        'start': start,
        'view_format': view_format,
        'filters': filters,
        'rc_page': rc_page
    }

def home(request):
    return render (request, 'calisphere/home.html', {'q': ''})

def itemView(request, item_id=''):
    item_id_search_term = 'id:"{0}"'.format(_fixid(item_id))
    item_solr_search = SOLR_select(q=item_id_search_term)
    if not item_solr_search.numFound:
        raise Http404("{0} does not exist".format(item_id))

    for item in item_solr_search.results:
        process_media(item)

    # TODO: write related objects version (else)
    if request.method == 'GET' and len(request.GET.getlist('q')) > 0:
        queryParams = processQueryRequest(request)
        carousel_items = itemViewCarousel(request, queryParams)

        return render(request, 'calisphere/itemView.html', {
            'item_solr_search': item_solr_search,
            'items': item_solr_search.results,
            'q': queryParams['q'],
            'rq': queryParams['rq'],
            'filters': queryParams['filters'],
            'rows': queryParams['rows'],
            'start': queryParams['start'],
            'search_results': carousel_items['results'],
            # 'facets': facets,
            'FACET_TYPES': FACET_TYPES,
            'numFound': carousel_items['numFound'],
            'pages': int(math.ceil(float(carousel_items['numFound'])/int(queryParams['rows']))),
            # 'view_format': queryParams['view_format'],
            # 'related_collections': relatedCollections(request, queryParams),
            # 'rc_page': queryParams['rc_page']
        })

        # return render (request, 'calisphere/home.html', {'q': q})

    return render(request, 'calisphere/itemView.html', {
        'q': '',
        'items': item_solr_search.results,
        'item_solr_search': item_solr_search,
    })


def search(request):
    if request.method == 'GET' and len(request.GET.getlist('q')) > 0:
        queryParams = processQueryRequest(request)

        # define facet fields to retrieve
        facet_fields = list(facet_type[0] for facet_type in FACET_TYPES)

        solr_search = SOLR_select(
            q=queryParams['query_terms'],
            rows=queryParams['rows'],
            start=queryParams['start'],
            fq=solrize_filters(queryParams['filters']),
            facet='true',
            facet_limit='-1',
            facet_field=facet_fields
        )

        # TODO: create a no results found page
        if len(solr_search.results) == 0: print 'no results found'

        for item in solr_search.results: process_media(item)

        # get facet counts
        facets = facetQuery(facet_fields, queryParams, solr_search)

        for i, facet_item in enumerate(facets['collection_data']):
            collection = (getCollectionData(collection_data=facet_item[0]), facet_item[1])
            facets['collection_data'][i] = collection
        for i, facet_item in enumerate(facets['repository_data']):
            repository = (getRepositoryData(repository_data=facet_item[0]), facet_item[1])
            facets['repository_data'][i] = repository

        filter_display = {}
        for filter_type in queryParams['filters']:
            if filter_type == 'collection_data':
                filter_display['collection_data'] = []
                for filter_item in queryParams['filters'][filter_type]:
                    collection = getCollectionData(collection_data=filter_item)
                    filter_display['collection_data'].append(collection)
            elif filter_type == 'repository_data':
                filter_display['repository_data'] = []
                for filter_item in queryParams['filters'][filter_type]:
                    repository = getRepositoryData(repository_data=filter_item)
                    filter_display['repository_data'].append(repository)
            else:
                filter_display[filter_type] = copy.copy(queryParams['filters'][filter_type])

        return render(request, 'calisphere/searchResults.html', {
            'q': queryParams['q'],
            'rq': queryParams['rq'],
            'filters': filter_display,
            'rows': queryParams['rows'],
            'start': queryParams['start'],
            'search_results': solr_search.results,
            'facets': facets,
            'FACET_TYPES': FACET_TYPES,
            'numFound': solr_search.numFound,
            'pages': int(math.ceil(float(solr_search.numFound)/int(queryParams['rows']))),
            'view_format': queryParams['view_format'],
            'related_collections': relatedCollections(request, queryParams),
            'num_related_collections': len(queryParams['filters']['collection_data']) if len(queryParams['filters']['collection_data']) > 0 else len(facets['collection_data']),
            'rc_page': queryParams['rc_page'],
            'form_action': reverse('calisphere:search')
        })

    return render (request, 'calisphere/home.html', {'q': ''})

def itemViewCarousel(request, queryParams={}):
    if not queryParams:
        if request.method == 'GET' and len(request.GET.getlist('q')) > 0:
            queryParams = processQueryRequest(request)

        ajaxRequest = True
        queryParams['rows'] = 6
    else:
        ajaxRequest = False

    # TODO: getting back way more fields than I really need
    carousel_solr_search = SOLR_select(
        q=queryParams['query_terms'],
        rows=queryParams['rows'],
        start=queryParams['start'],
        fq=solrize_filters(queryParams['filters'])
    )

    # except solr.SolrException:
        # TODO: better error handling
        # print solr.SolrException.reason
        # print solr.SolrException.httpcode
        # print solr.SolrException.body

    # search performed, process the results

    # TODO: create a no results found page
    if len(carousel_solr_search.results) == 0:
        print 'no results found'

    for item in carousel_solr_search.results:
        process_media(item)

    if ajaxRequest:
        return render(request, 'calisphere/carousel.html', {
            'q': queryParams['q'],
            'start': queryParams['start'],
            'numFound': carousel_solr_search.numFound,
            'search_results': carousel_solr_search.results,
        })

    return {'results': carousel_solr_search.results, 'numFound': carousel_solr_search.numFound}

def relatedCollections(request, queryParams={}):
    if not queryParams:
        queryParams = processQueryRequest(request)
        ajaxRequest = True
    else:
        ajaxRequest = False

    # #####################
    # get list of related collections
    # uncomment to get list of related collections disregarding any selected collection filters
    # #####################
    # if 'collection_name' in queryParams['filters'] and len(queryParams['filters']['collection_name']) > 0:
    #     related_collections_filters = {key: value for key, value in queryParams['filters'].items()
    #         if key != 'collection_name'}
    #     related_collections_filters['collection_name'] = []
    # else:
    related_collections_filters = queryParams['filters']

    related_collections_solr_search = SOLR_select(
        q=queryParams['query_terms'],
        rows='0',
        fq=solrize_filters(related_collections_filters),
        facet='true',
        facet_limit='-1',
        facet_field=['collection_data']
    )

    # remove collections with a count of 0 and sort by count
    related_collections_counts = process_facets(
        related_collections_solr_search.facet_counts['facet_fields']['collection_data'],
        queryParams['filters']['collection_data'] if 'collection_data' in queryParams['filters'] else []
    )

    # remove 'count'
    related_collections = list(facet for facet, count in related_collections_counts)

    three_related_collections = []
    for i in range(queryParams['rc_page']*3, queryParams['rc_page']*3+3):
        if len(related_collections) > i:
            facet = ["collection_data: \"" + related_collections[i] + "\""]
            collection_solr_search = SOLR_select(q=queryParams['query_terms'], rows='3', fq=facet, fields='collection_data, reference_image_md5, url_item, id, title')

            if len(collection_solr_search.results) > 0:
                if 'collection_data' in collection_solr_search.results[0] and len(collection_solr_search.results[0]['collection_data']) > 0:
                    collection = collection_solr_search.results[0]['collection_data'][0]

                    collection_data = {'image_urls': []}
                    for item in collection_solr_search.results:
                        process_media(item)
                        if 'reference_image_md5' in item:
                            collection_data['image_urls'].append({
                                'title': item['title'],
                                'reference_image_http': item['reference_image_http'],
                                'reference_image_md5': item['reference_image_md5']
                            })
                        else:
                            collection_data['image_urls'].append({
                                'title': item['title'],
                                'reference_image_http': item['reference_image_http']
                            })
                    collection_url = ''.join([
                        collection.rsplit('::')[0],
                        '?format=json'
                    ])
                    collection_json = urllib2.urlopen(collection_url).read()
                    collection_details = json.loads(collection_json)

                    collection_data['name'] = collection_details['name']
                    collection_data['resource_uri'] = collection_details['resource_uri']
                    col_id = re.match(r'^/api/v1/collection/(?P<collection_id>\d+)/$', collection_details['resource_uri'])
                    collection_data['collection_id'] = col_id.group('collection_id')

                    # TODO: get this from repository_data in solr rather than from the registry API
                    collection_data['institution'] = ''
                    # print collection_details
                    for repository in collection_details['repository']:
                        collection_data['institution'] = repository['name']
                        if repository['campus']:
                            collection_data['institution'] = collection_data['institution'] + ', '
                            for campus in repository['campus']:
                                collection_data['institution'] = collection_data['institution'] + campus['name'] + ', '

                    three_related_collections.append(collection_data)

    if not ajaxRequest:
        return three_related_collections
    else:
        return render(request, 'calisphere/related-collections.html', {
            'num_related_collections': len(related_collections),
            'related_collections': three_related_collections,
            'rc_page': queryParams['rc_page']
        })

def collectionsDirectory(request):
    solr_collections = CollectionManager(settings.SOLR_URL, settings.SOLR_API_KEY)
    collections = []

    page = int(request.GET['page']) if 'page' in request.GET else 1

    for collection_link in solr_collections.shuffled[(page*10)-10:page*10]:
        collections.append(getCollectionMosaic(collection_link.url))

    if 'page' in request.GET:
        return render(request, 'calisphere/collectionList.html', {'collections': collections, 'random': True, 'next_page': page+1})

    return render(request, 'calisphere/collectionsRandomExplore.html', {'collections': collections, 'random': True, 'next_page': page+1})

# TODO: doesn't handle non-letter characters
def collectionsAZ(request, collection_letter):
    solr_collections = CollectionManager(settings.SOLR_URL, settings.SOLR_API_KEY)

    collections_list = []
    if collection_letter == 'num':
        for collection_link in solr_collections.parsed:
            if collection_link.label[0] not in list(string.ascii_letters):
                collections_list.append(collection_link)
            else:
                break
    else:
        for collection_link in solr_collections.parsed:
            # TODO - diregard punctuation in position [0] of string, ie, when first character is a parens
            if collection_link.label[0] == collection_letter or collection_link.label[0] == collection_letter.upper():
                collections_list.append(collection_link)

    collections = []
    for collection_link in collections_list:
        collections.append(getCollectionMosaic(collection_link.url))

    return render(request, 'calisphere/collectionsAZ.html', {'collections': collections,
        'alphabet': list(string.ascii_uppercase),
        'collection_letter': collection_letter
    })

def collectionsSearch(request):
    return render(request, 'calisphere/collectionsTitleSearch.html', {'collections': [], 'collection_q': True})

def collectionView(request, collection_id):
    collection_url = 'https://registry.cdlib.org/api/v1/collection/' + collection_id + '/?format=json'
    collection_json = urllib2.urlopen(collection_url).read()
    collection_details = json.loads(collection_json)
    for repository in collection_details['repository']:
        repository['resource_id'] = repository['resource_uri'].split('/')[-2]

    # if request.method == 'GET' and len(request.GET.getlist('q')) > 0:
    queryParams = processQueryRequest(request)
    collection = getCollectionData(collection_id=collection_id)
    queryParams['filters']['collection_data'] = [collection['url'] + "::" + collection['name']]

    facet_fields = list(facet_type[0] for facet_type in FACET_TYPES if facet_type[0] != 'collection_data')

    # perform the search
    solr_search = SOLR_select(
        q=queryParams['query_terms'],
        rows=queryParams['rows'],
        start=queryParams['start'],
        fq=solrize_filters(queryParams['filters']),
        facet='true',
        facet_limit='-1',
        facet_field=facet_fields
    )

    for item in solr_search.results:
        process_media(item)

    facets = facetQuery(facet_fields, queryParams, solr_search)

    for i, facet_item in enumerate(facets['repository_data']):
        repository = (getRepositoryData(repository_data=facet_item[0]), facet_item[1])
        facets['repository_data'][i] = repository

    filter_display = {}
    for filter_type in queryParams['filters']:
        if filter_type == 'collection_data':
            filter_display['collection_data'] = []
        elif filter_type == 'repository_data':
            filter_display['repository_data'] = []
            for filter_item in queryParams['filters'][filter_type]:
                repository = getRepositoryData(repository_data=filter_item)
                filter_display['repository_data'].append(repository)
        else:
            filter_display[filter_type] = copy.copy(queryParams['filters'][filter_type])

    return render(request, 'calisphere/collectionView.html', {
        'q': queryParams['q'],
        'rq': queryParams['rq'],
        'filters': filter_display,
        'rows': queryParams['rows'],
        'start': queryParams['start'],
        'search_results': solr_search.results,
        'facets': facets,
        'FACET_TYPES': list((facet_type[0], facet_type[1]) for facet_type in FACET_TYPES if facet_type[0] != 'collection_data'),
        'numFound': solr_search.numFound,
        'pages': int(math.ceil(float(solr_search.numFound)/int(queryParams['rows']))),
        'view_format': queryParams['view_format'],
        'collection': collection_details,
        'form_action': reverse('calisphere:collectionView', kwargs={'collection_id': collection_id})
    })

def campusDirectory(request):
    repositories_solr_query = SOLR_select(q='*:*', rows=0, start=0, facet='true', facet_field=['repository_data'], facet_limit='-1')
    solr_repositories = repositories_solr_query.facet_counts['facet_fields']['repository_data']

    repositories = []
    for repository_data in solr_repositories:
        repository = getRepositoryData(repository_data=repository_data)
        if repository['campus']:
            repositories.append({
                'name': repository['name'],
                'campus': repository['campus'],
                'repository_id': re.match(r'https://registry\.cdlib\.org/api/v1/repository/(?P<repository_id>\d*)/?', repository['url']).group('repository_id')
            })

    repositories = sorted(repositories, key=lambda repository: (repository['campus'], repository['name']))
    # Use hard-coded campus list so UCLA ends up in the correct order
    # campuses = sorted(list(set([repository['campus'] for repository in repositories])))

    return render(request, 'calisphere/campusDirectory.html', {'repositories': repositories,
        'campuses': CAMPUS_LIST})

def statewideDirectory(request):
    repositories_solr_query = SOLR_select(q='*:*', rows=0, start=0, facet='true', facet_field=['repository_data'], facet_limit='-1')
    solr_repositories = repositories_solr_query.facet_counts['facet_fields']['repository_data']

    repositories = []
    for repository_data in solr_repositories:
        repository = getRepositoryData(repository_data=repository_data)
        if repository['campus'] == '':
            repositories.append({
                'name': repository['name'],
                'repository_id': re.match(r'https://registry\.cdlib\.org/api/v1/repository/(?P<repository_id>\d*)/?', repository['url']).group('repository_id')
            })

    binned_repositories = []
    bin = []
    for repository in repositories:
        if repository['name'][0] in string.punctuation:
            bin.append(repository)
    if len(bin) > 0:
        binned_repositories.append({'punctuation': bin})

    for char in string.ascii_uppercase:
        bin = []
        for repository in repositories:
            if repository['name'][0] == char or repository['name'][0] == char.upper:
                bin.append(repository)
        if len(bin) > 0:
            binned_repositories.append({char: bin})

    return render(request, 'calisphere/statewideDirectory.html', {'state_repositories': binned_repositories})

def campusView(request, campus_slug, subnav=False):
    campus_id = ''
    for campus in CAMPUS_LIST:
        if campus_slug == campus['slug']:
            campus_id = campus['id']
    if campus_id == '':
        print "Campus registry ID not found"

    campus_url = 'https://registry.cdlib.org/api/v1/campus/' + campus_id + '/'
    campus_json = urllib2.urlopen(campus_url + "?format=json").read()
    campus_details = json.loads(campus_json)

    contact_information = json.loads(
        urllib2.urlopen("http://dsc.cdlib.org/institution-json/" + campus_details['ark']).read())

    if subnav == 'institutions':
        campus_fq = ['campus_url: "' + campus_url + '"']

        institutions_solr_search = SOLR_select(
            q='',
            rows=0,
            start=0,
            fq=campus_fq,
            facet='true',
            facet_limit='-1',
            facet_field = ['collection_data', 'repository_data']
        )

        related_institutions = list(institution[0] for institution in process_facets(institutions_solr_search.facet_counts['facet_fields']['repository_data'], []))

        for i, related_institution in enumerate(related_institutions):
            related_institutions[i] = getRepositoryData(repository_data=related_institution)

        return render(request, 'calisphere/campusInstitutionsView.html', {
            'campus_slug': campus_slug,
            'institutions': related_institutions,
            'campus': campus_details,
            'contact_information': contact_information
        })

    elif subnav == 'collections':
        campus_fq = ['campus_url: "' + campus_url + '"']

        collections_solr_search = SOLR_select(
            q='',
            rows=0,
            start=0,
            fq=campus_fq,
            facet='true',
            facet_limit='-1',
            facet_field = ['collection_data', 'repository_data']
        )

        related_collections = list(collection[0] for collection in process_facets(collections_solr_search.facet_counts['facet_fields']['collection_data'], []))

        for i, related_collection in enumerate(related_collections):
            collection_data = getCollectionData(collection_data=related_collection)

            related_collections[i] = getCollectionMosaic(collection_data['url'])

        return render(request, 'calisphere/campusCollectionsView.html', {
            'campus_slug': campus_slug,
            'collections': related_collections,
            'campus': campus_details,
            'contact_information': contact_information
        })

    queryParams = processQueryRequest(request)

    fq = solrize_filters(queryParams['filters'])
    fq.append('campus_url: "https://registry.cdlib.org/api/v1/campus/' + campus_id + '/"')

    facet_fields = list(facet_type[0] for facet_type in FACET_TYPES)

    solr_search = SOLR_select(
        q=queryParams['query_terms'],
        rows=queryParams['rows'],
        start=queryParams['start'],
        fq=fq,
        facet='true',
        facet_limit='-1',
        facet_field=facet_fields
    )

    for item in solr_search.results:
        process_media(item)

    facets = facetQuery(facet_fields, queryParams, solr_search)

    for i, facet_item in enumerate(facets['collection_data']):
        collection = (getCollectionData(collection_data=facet_item[0]), facet_item[1])
        facets['collection_data'][i] = collection

    for i, facet_item in enumerate(facets['repository_data']):
        repository = (getRepositoryData(repository_data=facet_item[0]), facet_item[1])
        facets['repository_data'][i] = repository

    filter_display = {}
    for filter_type in queryParams['filters']:
        if filter_type == 'repository_data':
            filter_display['repository_data'] = []
            for filter_item in queryParams['filters'][filter_type]:
                repository = getRepositoryData(repository_data=filter_item)
                filter_display['repository_data'].append(repository)
        elif filter_type == 'collection_data':
            filter_display['collection_data'] = []
            for filter_item in queryParams['filters'][filter_type]:
                collection = getCollectionData(collection_data=filter_item)
                filter_display['collection_data'].append(collection)
        else:
            filter_display[filter_type] = copy.copy(queryParams['filters'][filter_type])

    return render(request, 'calisphere/campusView.html', {
        'q': queryParams['q'],
        'rq': queryParams['rq'],
        'filters': filter_display,
        'rows': queryParams['rows'],
        'start': queryParams['start'],
        'search_results': solr_search.results,
        'facets': facets,
        'FACET_TYPES': list((facet_type[0], facet_type[1]) for facet_type in FACET_TYPES),
        'numFound': solr_search.numFound,
        'pages': int(math.ceil(float(solr_search.numFound)/int(queryParams['rows']))),
        'view_format': queryParams['view_format'],
        'campus': campus_details,
        'contact_information': contact_information,
        'form_action': reverse('calisphere:campusView', kwargs={'campus_slug': campus_slug}),
        'campus_slug': campus_slug
    })

def repositoryView(request, repository_id, collections=False):
    repository_json = urllib2.urlopen('https://registry.cdlib.org/api/v1/repository/' + repository_id + '/?format=json').read()
    repository_details = json.loads(repository_json)

    contact_information = json.loads(
        urllib2.urlopen("http://dsc.cdlib.org/institution-json/" + repository_details['ark']).read())

    queryParams = processQueryRequest(request)
    repository = getRepositoryData(repository_id=repository_id)
    queryParams['filters']['repository_data'] = [repository['url'] + "::" + repository['name']]
    if 'campus' in repository and repository['campus']:
        queryParams['filters']['repository_data'][0] = queryParams['filters']['repository_data'][0] + "::" + repository['campus']

    if collections == 'collections':
        if 'campus' in repository and repository['campus']:
            collections_fq = ['repository_data: "' + repository['url'] + '::' + repository['name'] + '::' + repository['campus'] + '"']
        else:
            collections_fq = ['repository_data: "' + repository['url'] + '::' + repository['name'] + '"']

        collections_solr_search = SOLR_select(
            q='',
            rows=0,
            start=0,
            fq=collections_fq,
            facet='true',
            facet_limit='-1',
            facet_field = ['collection_data', 'repository_data']
        )

        related_collections = list(collection[0] for collection in process_facets(collections_solr_search.facet_counts['facet_fields']['collection_data'], []))

        for i, related_collection in enumerate(related_collections):
            collection_data = getCollectionData(collection_data=related_collection)

            related_collections[i] = getCollectionMosaic(collection_data['url'])

        return render(request, 'calisphere/repositoryCollectionsView.html', {
            'repository_id': repository_id,
            'collections': related_collections,
            'repository': repository_details,
            'contact_information': contact_information
        })

    else:
        # if request.method == 'GET' and len(request.GET.getlist('q')) > 0:
        facet_fields = list(facet_type[0] for facet_type in FACET_TYPES if facet_type[0] != 'repository_data')

        # perform the search
        solr_search = SOLR_select(
            q=queryParams['query_terms'],
            rows=queryParams['rows'],
            start=queryParams['start'],
            fq=solrize_filters(queryParams['filters']),
            facet='true',
            facet_limit='-1',
            facet_field=facet_fields
        )

        for item in solr_search.results:
            process_media(item)

        facets = facetQuery(facet_fields, queryParams, solr_search)

        for i, facet_item in enumerate(facets['collection_data']):
            collection = (getCollectionData(collection_data=facet_item[0]), facet_item[1])
            facets['collection_data'][i] = collection

        filter_display = {}
        for filter_type in queryParams['filters']:
            if filter_type == 'repository_data':
                filter_display['repository_data'] = []
            elif filter_type == 'collection_data':
                filter_display['collection_data'] = []
                for filter_item in queryParams['filters'][filter_type]:
                    collection = getCollectionData(collection_data=filter_item)
                    filter_display['collection_data'].append(collection)
            else:
                filter_display[filter_type] = copy.copy(queryParams['filters'][filter_type])

        return render(request, 'calisphere/repositoryView.html', {
            'q': queryParams['q'],
            'rq': queryParams['rq'],
            'filters': filter_display,
            'rows': queryParams['rows'],
            'start': queryParams['start'],
            'search_results': solr_search.results,
            'facets': facets,
            'FACET_TYPES': list((facet_type[0], facet_type[1]) for facet_type in FACET_TYPES if facet_type[0] != 'repository_data'),
            'numFound': solr_search.numFound,
            'pages': int(math.ceil(float(solr_search.numFound)/int(queryParams['rows']))),
            'view_format': queryParams['view_format'],
            'repository': repository_details,
            'contact_information': contact_information,
            'repository_id': repository_id,
            'form_action': reverse('calisphere:repositoryView', kwargs={'repository_id': repository_id})
        })

def _fixid(id):
    return re.sub(r'^(\d*--http:/)(?!/)', r'\1/', id)
