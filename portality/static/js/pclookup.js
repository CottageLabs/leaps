jQuery(function ($) {
  jQuery(document).ready(function() {
    var schools = {};
    var getSchools = function() {
      $.ajax({
        url: 'https://leapssurvey.org/query/school/_search?size=100&q=NOT%20name:TEST',
        type: 'POST',
        dataType: 'JSONP',
        success: function(data) {
          var list = [];
          for ( var h in data.hits.hits ) {
            list.push(data.hits.hits[h]._source.name);
            schools[data.hits.hits[h]._source.name] = data.hits.hits[h]._source;
          }
          list.sort();
          var opts = '<option></option>';
          for ( var l in list ) {
            opts += '<option>' + list[l] + '</option>';
          }
          $('#leaps_pc_school').html(opts);
        }
      });
    }
    getSchools();

    var schoolCheck = function(e) {
      $('.leaps_pc_statements').hide();
      $('#leaps_pc_lookup').val('');
      if (schools[$('#leaps_pc_school').val()].leaps_category === "1+") {
        $('#leaps_pc_search').hide();
        $('#leaps_pc_cat1plus').show();
      } else if (parseInt(schools[$('#leaps_pc_school').val()].leaps_category) === 1) {
        $('#leaps_pc_search').hide();
        $('#leaps_pc_cat1').show();
      } else {
        $('#leaps_pc_search').show();
      }
    }
    $('#leaps_pc_school').bind('change',schoolCheck);

    var simds = {};
    var chosen = function(e,pc) {
      if (e) e.preventDefault();
      $('#leaps_pc_result').html('');
      //if (pc === undefined) pc = $(this).html();
      if ( parseInt(simds[pc]) <= 2 ) {
        $('#leaps_pc_lookup').val(pc);
        $('#leaps_pc_simd_1_2').show();
      } else if ( parseInt(simds[pc]) <= 10 ) {
        $('#leaps_pc_lookup').val(pc);
        $('#leaps_pc_simd_3_10').show();
        $('#leaps_pc_simd_other').show();
      } else {
        $('#leaps_pc_simd_unknown').show();
        $('#leaps_pc_simd_other').show();
      }
    }

    var lookup = function(e) {
      $('.leaps_pc_statements').hide();
      if (e.keyCode !== 13) {
        $.ajax({
          url: 'https://leapssurvey.org/query/simd/_search' + '?size=20&sort=post_code&size=10&q=id:' + $('#leaps_pc_lookup').val().toLowerCase().replace(/ /g,'') + '*',
          type: 'POST',
          dataType: 'JSONP',
          success: function(data) {
            $('.leaps_pc_choose').unbind('click',chosen);
            var res = '';
            for ( var r in data.hits.hits ) {
              var rec = data.hits.hits[r]._source;
              simds[rec.post_code] = rec.simd_decile;
              res += '<a href="#" class="leaps_pc_choose">' + rec.post_code + '</a>';
              res += '<br>';
            }
            if (data.hits.hits.length === 1) {
              $('#leaps_pc_result').html('');
              chosen(undefined,data.hits.hits[0]._source.post_code);
            } else {
              $('#leaps_pc_result').html(res);
              //$('.leaps_pc_choose').bind('click',chosen);
              chosen();
            }
          }
        });
      }
    }
    $('#leaps_pc_lookup_trigger').bind('click',lookup);
  });
});