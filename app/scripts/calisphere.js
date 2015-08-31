/*global _, QueryManager, GlobalSearchForm, FacetForm, CarouselContext, ComplexCarousel, ContactOwnerForm */

'use strict';

if(typeof console === 'undefined') {
  console = { log: function() { } };
}

$(document).on('pjax:timeout', function() { return false; });

var qm, globalSearchForm, facetForm, carousel, complexCarousel, DESKTOP, contactOwnerForm, popstate = null;

var setupObjects = function() {
  if ($('#js-facet').length > 0) {
    if (facetForm === undefined) {
      facetForm = new FacetForm({model: qm});
      facetForm.listening = true;
    }
    else if (facetForm.listening === false) {
      facetForm.initialize();
      facetForm.delegateEvents();
      facetForm.listening = true;
    }
    facetForm.toggleSelectDeselectAll();

    // get rid of any visible tooltips
    var visibleTooltips = $('[data-toggle="tooltip"][aria-describedby]');
    for (var i=0; i<visibleTooltips.length; i++) {
      var tooltipId = $(visibleTooltips[i]).attr('aria-describedby');
      $('#' + tooltipId).remove();
    }
    // set tooltips
    $('[data-toggle="tooltip"]').tooltip({
      placement: 'top'
    });
  }
  else if (facetForm !== undefined) {
    facetForm.stopListening();
    facetForm.undelegateEvents();
    facetForm.listening = false;
  }

  if($('#js-carouselContainer').length > 0) {
    if (carousel === undefined) {
      carousel = new CarouselContext({model: qm});
      carousel.listening = true;
    }
    else if (carousel.listening === false) {
      carousel.initialize();
      carousel.delegateEvents();
      carousel.listening = true;
    }
  }
  else if (carousel !== undefined) {
    carousel.stopListening();
    carousel.undelegateEvents();
    carousel.listening = false;
  }

  if($('#js-contactOwner').length > 0) {
    if (contactOwnerForm === undefined) {
      contactOwnerForm = new ContactOwnerForm();
      contactOwnerForm.listening = true;
    }
    else if (contactOwnerForm.listening === false) {
      contactOwnerForm.initialize();
      contactOwnerForm.delegateEvents();
      contactOwnerForm.listening = true;
    }
  } else if (contactOwnerForm !== undefined) {
    contactOwnerForm.stopListening();
    contactOwnerForm.undelegateEvents();
    contactOwnerForm.listening = false;
  }

  if($('.carousel-complex').length > 0) {
    if (complexCarousel === undefined) {
      complexCarousel = new ComplexCarousel({model: qm});
      $('.js-obj__osd-infobanner').show();
      complexCarousel.listening = true;
    }
    else if (complexCarousel.listening === false) {
      complexCarousel.initialize();
      complexCarousel.delegateEvents();
      $('.js-obj__osd-infobanner').show();
      complexCarousel.listening = true;
    } else {
      $('.js-obj__osd-infobanner').hide();
      complexCarousel.initialize();
    }
    //TODO: this should only have to happen once!
    $('.js-obj__osd-infobanner-link').click(function(){
      $('.js-obj__osd-infobanner').slideUp('fast');
    });
  }
  else if (complexCarousel !== undefined) {
    complexCarousel.stopListening();
    complexCarousel.undelegateEvents();
    complexCarousel.listening = false;
  }

  //if we've gotten to a page with a list of collection mosaics, init infinite scroll
  //TODO: change reference to localhost!
  if($('#js-mosaicContainer').length > 0) {
    $('#js-mosaicContainer').infinitescroll({
      navSelector: '#js-collectionPagination',
      nextSelector: '#js-collectionPagination a.js-next',
      itemSelector: '#js-mosaicContainer div.js-collectionMosaic',
      debug: false,
      loading: {
        finishedMsg: 'All collections showing.',
        img: 'http://calisphere.cdlib.org/static_root/images/orange-spinner.gif',
        msgText: '',
        selector: '#js-loading'
      }
    });
  }
};

$(document).ready(function() {
  $('html').removeClass('no-jquery');
  if ($(window).width() > 900) { DESKTOP = true; }
  else { DESKTOP = false; }

  $.pjax.defaults.timeout = 5000;
  $(document).pjax('a[data-pjax=js-pageContent]', '#js-pageContent');

  qm = new QueryManager();
  globalSearchForm = new GlobalSearchForm({model: qm});
  setupObjects();

  $('#js-global-header-logo').on('click', function() {
    if (!_.isEmpty(qm.attributes) || !_.isEmpty(sessionStorage)) {
      qm.clear();
    }
  });

  $(document).on('pjax:beforeSend', '#js-itemContainer', function(e, xhr, options) {
    if (options.container === '#js-itemContainer') {
      xhr.setRequestHeader('X-From-Item-Page', 'true');
    }
  });

  $(document).on('pjax:beforeReplace', '#js-pageContent', function() {
    if($('#js-mosaicContainer').length > 0) {
      $('#js-mosaicContainer').infinitescroll('destroy');
    }
  });

  $(document).on('pjax:end', '#js-itemContainer', function() {
    var lastItem = $('.carousel__item--selected');
    if (lastItem.children('a').data('item_id') !== qm.get('itemId')) {
      lastItem.find('.carousel__image--selected').toggleClass('carousel__image');
      lastItem.find('.carousel__image--selected').toggleClass('carousel__image--selected');
      lastItem.toggleClass('carousel__item');
      lastItem.toggleClass('carousel__item--selected');

      var linkItem = $('.js-item-link[data-item_id="' + qm.get('itemId') + '"]');
      linkItem.find('.carousel__image').toggleClass('carousel__image--selected');
      linkItem.find('.carousel__image').toggleClass('carousel__image');
      linkItem.parent().toggleClass('carousel__item--selected');
      linkItem.parent().toggleClass('carousel__item');
    }
  });

  $(document).on('pjax:end', '#js-pageContent', function() {
    //if we've gotten to a page without search context, clear the query manager
    if($('#js-facet').length <= 0 && $('#js-objectViewport').length <= 0) {
      qm.clear({silent: true});
    }

    if (popstate === 'back' || popstate === 'forward') {
      _.each($('form'), function(form) {
        form.reset();
        if ($(form).attr('id') === 'js-facet' || $(form).attr('id') === 'js-carouselForm') {
          var formAfter = _.map($(form).serializeArray(), function(value) { return [value.name, value.value]; });
          for (var i=0; i<formAfter.length; i++) {
            for (var j=i+1; j<formAfter.length; j++) {
              if (formAfter[i][0] === formAfter[j][0]) {
                formAfter[i][1] = [formAfter[i][1], formAfter[j][1]];
                formAfter[i][1] = _.flatten(formAfter[i][1]);
                formAfter.splice(j, 1);
                j = j-1;
              }
            }
          }
          formAfter = _.object(formAfter);
          formAfter = _.defaults(formAfter, {type_ss: '', facet_decade: '', repository_data: '', collection_data: ''});

          qm.set(formAfter, {silent: true});
        }
      });
    }
    
    popstate = null;
    
    setupObjects();
  });

  $(document).on('pjax:popstate', '#js-pageContent', function(e) {
    popstate = e.direction;
  });

  $(document).on('pjax:end', function() {
    // send google analytics on pjax pages
    /* globals ga: false */
    if (typeof ga !== 'undefined') {
      ga('set', 'location', window.location.href);
      ga('send', 'pageview');
    }
  });

  $(document).on('pjax:send', function() {
    $('#loading').show();
  });

  $(document).on('pjax:complete', function() {
    $('#loading').hide();
  });

});

$(document).on('ready pjax:end', function() {
  // google analytics that need to read stuff
  // might move all of it here, just to keep it all the same
  // right now, just institution specific code
  var inst_ga_code = $('[data-ga-code]').data('ga-code');
  if (inst_ga_code) {
    var inst_tracker_name = inst_ga_code.replace(/-/g,'x');
    if (typeof ga !== 'undefined') {
      ga('create', inst_ga_code, 'auto', {'name': inst_tracker_name});
      ga( inst_tracker_name + '.set', 'location', window.location.href);
      ga( inst_tracker_name + '.send', 'pageview');
    }
  }

  // collection title search

  /* globals Bloodhound: false */
  if ($('#titlesearch__field').length) {
    var collections = new Bloodhound({
      datumTokenizer: Bloodhound.tokenizers.obj.whitespace('title'),
      queryTokenizer: Bloodhound.tokenizers.whitespace,
      prefetch: '/collections/titles.json'
    });
    // chain things to the titlesearch field
    $('#titlesearch__field').typeahead(null, {
      name: 'collections',
      display: 'title',
      limit: 10,
      source: collections
    }).on('keydown', function(event) {
      // disable enter
      // http://stackoverflow.com/a/21318996/1763984
      var x = event.which;
      if (x === 13) {
       event.preventDefault();
      }
    }).bind('typeahead:selected', function(obj, datum) {
      // redirect to the select page
      window.location = datum.uri;
    });
  } // end title search
});

if(!('backgroundBlendMode' in document.body.style)) {
    // No support for background-blend-mode
  var html = document.getElementsByTagName('html')[0];
  html.className = html.className + ' no-background-blend-mode';
}
