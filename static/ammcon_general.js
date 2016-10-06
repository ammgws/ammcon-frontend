// registers this click event handler on 'document ready'
/*
$(function() {
    $("a#login").bind('click', function() {
        $("#loader").show();
        //alert("Click event detected.");
        //window.console&&console.log("Click event detected.");
    });
});
*/

$(document).on( "click", ".show-page-loading-msg", function() {
  var $this = $( this ),
  theme = $this.jqmData( "theme" ) || $.mobile.loader.prototype.options.theme,
  /* msgText = $this.jqmData( "msgtext" ) || $.mobile.loader.prototype.options.text,*/
  msgText = "Logging you into AmmCon",
  textVisible = $this.jqmData( "textvisible" ) || $.mobile.loader.prototype.options.textVisible,
  textonly = !!$this.jqmData( "textonly" );
  html = $this.jqmData( "html" ) || "";
$.mobile.loading( 'show', {
  text: msgText,
  textVisible: textVisible,
  theme: theme,
  textonly: textonly,
  html: html
  });
});