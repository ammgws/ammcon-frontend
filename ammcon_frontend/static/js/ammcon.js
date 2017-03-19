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
        ttl : 2000
    });
}

// Update temperatures shown in SVG.
temp_update = function (temp_command, enable_notifications=true) {
    $.getJSON($SCRIPT_ROOT + '/data/' + temp_command.substring(4), {}, function(data) {
          // If not authorised, redirect back to homepage.
          if (data.redirect) {
            window.location.replace(data.redirect);
          }
          else {
            if (data.temperature != null) {
                document.getElementById(temp_command).textContent = data.temperature + "°C " + data.humidity + "%";
            }
            else {
                // Otherwise no data was returned by the backend.
                if (enable_notifications == true) {
                    notify("No data available - sensor offline?");
                }
            }
          }
        });
}

// Call backend when user clicks on a command in command menu.
// This event handler is registered on 'document ready'.
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

// Load house layout SVG and register the various click handlers.
$(function() {
    $('#layout_main').load($SCRIPT_ROOT + 'static/layout.svg', null, function(data, status, xhr) {
        //TODO: refactor code, reuse functions etc

        // Update temperature values on first load (but disable notifications).
        temp_update("temp1", false);
        temp_update("temp2", false);
        temp_update("temp3", false);

        // Register click handlers to allow user to refresh temps.
        $('#temp1').click(function() {
            temp_update("temp1");
        });
        $('#temp2').click(function() {
            temp_update("temp2");
        });
        $('#temp3').click(function() {
            temp_update("temp3");
        });

        // Register click handlers for lights, aircon, etc.
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

