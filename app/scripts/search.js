"use strict";

/**
 *  @file       search.js
 *  
 *  @author     Amy Wieliczka <amywieliczka [at] berkeley.edu>
 **/

function FacetQuery(params) {
  $(document).on('submit', '#facet', function(container) {
    return function(event) {
      $.pjax.submit(event, container);
    }
  }('#searchResults'));
  
  
  //***********ITEM VIEW**************//
  $(document).on('click', '.item-thumb', function() {
    $('#item_id').prop('value', $(this).data('item_id'));
    $('#item-view > input[name=start]').prop('value', $('.item-thumb').index(this));
    $('#item-view').submit(function(that) {
      return function(e) {
        $(this).prop('action', '/' + $(that).data('item_id') + "/");
        return;
      }
    }(this));
    $('#item-view').submit();
  });

  //*************FACETING*************//
  $(document).on('change', '.facet', function() {
    $('#facet').submit();
  });

  $(document).on('click', '.filter-pill', function() {
    $("#" + $(this).data('slug')).prop('checked', false);
    $('#facet').submit();
  });
  
  $(document).on('click', '#deselect-facets', function() {
    $('.facet').prop('checked', false);
    $('#facet').submit();
  });
  
  $(document).on('click', '.select-facets', function() {
    // $('.facet-{{ facet_type }}').prop('checked', true); 
    $(this).parents('.facet-type').find('.facet').prop('checked', true);
    $('#facet').submit();
  });
  
  // var repository_autocomplete = new Autocomplete($('#repository_name'));
  // var collection_autocomplete = new Autocomplete($('#collection_name'));
  
  // ***********PAGINATION**********
  
  $(document).on('click', '#view16', function() {
    $('#rows').prop('value', '16'); 
    $('#facet').submit();
  });
  
  $(document).on('click', '#view50', function() {
    $('#rows').prop('value', '50'); 
    $('#facet').submit();
  });
  
  $(document).on('click', '#prev', function() {
    $('#start').val($(this).data('start')); 
    $('#facet').submit();
  });
  
  $(document).on('change', '#start', function() {
    $('#facet').submit();
  });
  
  $(document).on('click', '#next', function() {
    $('#start').val($(this).data('start')); 
    $('#facet').submit();
  });
  
  // ***************VIEW FORMAT*************
  
  $(document).on('click', '#thumbnails', function() {
    $('#view_format').prop('value', 'thumbnails'); $('#facet').submit();
  });
  
  $(document).on('click', '#list', function() {
    $('#view_format').prop('value', 'list'); $('#facet').submit();
  });
}

// takes two jquery selectors: search input, and pjax container for search results
function Search(params) {
  this.search = params.search;
  this.container = params.container;
  
  $(document).on('submit', this.search, function(container) {
    return function(event) {
      $.pjax.submit(event, container);
    }
  }(this.container));
  
  this.searchResults = new FacetQuery();
}

$(document).ready(function() {
  var search = new Search({search: '#searchForm', container: '#searchResults'});
});