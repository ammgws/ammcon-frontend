// call backend when user clicks on a command in command menu
// this event handler is registered on 'document ready'
$(function() {
  $('[data-ammcon]').bind('click', function() {
    $.getJSON($SCRIPT_ROOT + '/command', {
      command: $(this).data("ammcon_cmd")
    }, function(data) {
      // redirect back to homepage to reauthorise
      if (data.redirect) {
        window.location.replace(data.redirect);
      }
      else {
        $("#response").text(data.response + '@' + data.time);

        // use nd2 toast to display response
        new $.nd2Toast({
            message : data.response + '@' + data.time,
            action : {
                title : "Info",
                fn : function() {
                    console.log("Not implemented yet");
                },
                color : "lime"
            },
            ttl : 3000
        });

      }
    });
    $('[data-role=panel]').panel("close");
    return false;
  });
});

// on click, update the displayed temperature/humidity for the given room
// this event handler is registered on 'document ready'
$(function() {
  $('.temp').bind('click', function() {
    temp_command = $(this).attr("id");
    // for debugging purposes:
    //alert(temp_command)
    $.getJSON($SCRIPT_ROOT + '/data/' + temp_command.substring(4), {

    }, function(data) {
      // redirect back to homepage to reauthorise
      if (data.redirect) {
        window.location.replace(data.redirect);
        //$(location).attr('href', data.redirect));
      }
      else {
        //window.console&&console.log(moment(data.datetime).format("Y/mm/dd_HH:MM:SS"));
        if (data.temperature != null) {
            $("#" + temp_command).text(data.temperature + "°C " + data.humidity + "%");
            $("#" + temp_command).attr("title", "Data from " + moment(data.datetime).format("Y/MM/DD HH:MM:SS"));
        }
        else {
            //do nothing

            // use nd2 toast to display error message
            new $.nd2Toast({
                message : "No data available - sensor offline?",
                action : {
                    title : "Info",
                    fn : function() {
                        console.log("Not implemented yet");
                    },
                    color : "lime"
                },
                ttl : 3000
            });

        }
      }
    });
    return false;
  });
});
