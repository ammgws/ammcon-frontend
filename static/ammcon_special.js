// on click, show popup menu for commands
// registers this change event handler on 'document ready'
$(function() {
  $('.commands').bind('click', function() {
    $.getJSON($SCRIPT_ROOT + '/command', {
      command: $(this).attr("value"),
    }, function(data) {
      // redirect back to homepage to reauthorise
      if (data.redirect) {
        window.location.replace(data.redirect);
        //$(location).attr('href', data.redirect));
      }
      else {
        // close popup first for better user experience?
        //$($(this).attr("yip")).popup("close");
        $("#response").text(data.response + '@' + data.time);
      }
    });
    // for debugging purposes:
    // alert($(this).attr("yip"))
    $($(this).attr("yip")).popup("close");
    return false;
  });
});

// on click, update the displayed temperature/humidity for the given room
// registers this change event handler on 'document ready'
$(function() {
  $('.temp').bind('click', function() {
    temp_command = $(this).attr("id")
    // for debugging purposes:
    //alert(temp_command)
    $.getJSON($SCRIPT_ROOT + '/command', {
      command: temp_command,
    }, function(data) {
      // redirect back to homepage to reauthorise
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