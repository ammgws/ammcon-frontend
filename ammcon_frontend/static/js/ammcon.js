log = function (message) {
    window.console&&console.log(message);
}

notify = function(message) {
    new $.nd2Toast({
        message : message,
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

temp_function = function (temp_command) {
    $.getJSON($SCRIPT_ROOT + '/data/' + temp_command.substring(4), {
        }, function(data) {
          // redirect back to homepage to reauthorise
          if (data.redirect) {
            window.location.replace(data.redirect);
          }
          else {
            if (data.temperature != null) {
                //log(data.temperature + "°C " + data.humidity + "%")
                return data.temperature + "°C " + data.humidity + "%";
            }
            else{
                return false;
            }
          }
        });
        return false;
}

// call backend when user clicks on a command in command menu
// this event handler is registered on 'document ready'
$(function() {
  $('[data-ammcon]').on('click', function() {
    $.getJSON($SCRIPT_ROOT + '/command', {
      command: $(this).data("ammcon_cmd")
    }, function(data) {
      // redirect back to homepage to reauthorise
      if (data.redirect) {
        window.location.replace(data.redirect);
      }
      else {
        $("#response").text(data.response + '@' + data.time);
        // use nd2 toast-notify to display response
        notify(data.response + '@' + data.time);
      }
    });
    $('[data-role=panel]').panel("close");
    return false;
  });
});

// on click, update the displayed temperature/humidity for the given room
// this event handler is registered on 'document ready'
$(function() {
  $('.temp').on('click', function() {
    temp_command = $(this).attr("id");
    // for debugging purposes:
    //alert(temp_command)
    //log(temp_command)
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

            document.getElementById('temp1').textContent = data.temperature + "°C " + data.humidity + "%";

        }
        else {
            //do nothing
            // use nd2 toast-notify to display error message
            notify("No data available - sensor offline?");
        }
      }
    });
    return false;
  });
});

$(function() {
    $('#layout_main').load($SCRIPT_ROOT + 'static/layout.svg', null, function(data, status, xhr) {

        //TODO: refactor code, reuse functions etc

        //document.getElementById('temp1').textContent = temp_function("temp1");

        document.getElementById('temp1').textContent = temp_function("temp1");
        document.getElementById('temp2').textContent = temp_function("temp2");
        document.getElementById('temp3').textContent = temp_function("temp3");
        $('#temp1').click(function() {
            //temp_function("temp1");
            document.getElementById('temp1').textContent = "18.25°C 37%"
        });
        $('#temp2').click(function() {
            document.getElementById('temp2').textContent = "19.25°C 35%"
        });
        $('#temp3').click(function() {
            document.getElementById('temp3').textContent = "17.25°C 36%"
        });

        $("#living_light1").click(function() {
            $("#living1_light_menu").panel("open");
        });
        $("#living_light2").click(function() {
            $("#living2_light_menu").panel("open");
        });
        $("#bedroom1_light1").click(function() {
            $("#bedroom1_light_menu").panel("open");
        });
        $("#bedroom2_light1").click(function() {
            $("#bedroom2_light_menu").panel("open");
        });
        $("#bedroom3_light1").click(function() {
            $("#bedroom3_light_menu").panel("open");
        });

        $("#tv").click(function() {
            $("#tv_menu").panel("open");
        });

        $("#living_aircon").click(function() {
            $("#living_aircon_menu").panel("open");
        });
        $("#bedroom2_aircon").click(function() {
            $("#bedroom2_aircon_menu").panel("open");
        });
        $("#bedroom3_aircon").click(function() {
            $("#bedroom3_aircon_menu").panel("open");
        });

    });
});

