// on click, show popup menu for light commands
// register change event handler on 'document ready'
$(function() {
  $('.commands').bind('click', function() {
    $.getJSON($SCRIPT_ROOT + '/command', {
      command: $(this).attr("value"),
    }, function(data) {
      if (data.redirect) {
        window.location.replace(data.redirect);
        //$(location).attr('href', data.redirect));
      }
      else {
        $("#response").text(data.response + '@' + data.time);
      }
    });
    // for debugging purposes:
    // alert($(this).attr("yip"))
    $($(this).attr("yip")).popup("close");
    return false;
  });
});

// on click, update temperature/humidity for the given room
// register change event handler on 'document ready'
$(function() {
  $('.temp').bind('click', function() {
    temp_command = $(this).attr("id")
    // for debugging purposes:
    //alert(temp_command)
    $.getJSON($SCRIPT_ROOT + '/command', {
      command: temp_command,
    }, function(data) {
      if (data.redirect) {
        window.location.replace(data.redirect);
        //$(location).attr('href', data.redirect));
      }
      else {
        $("#" + temp_command).text(data.response);
      }
    });
    return false;
  });
});