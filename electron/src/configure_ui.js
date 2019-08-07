const $ = window.$ = window.jQuery = require('jquery');
window.Bootstrap = require('bootstrap');

var {ConfigureStore} = require('./configure_store');
ConfigureStore.init();

function onTextChange(e) {
  let $ele = $(e.currentTarget);
  ConfigureStore.set($ele.attr('name'), $ele.val());
}

function onCheckChange(e) {
  let $ele = $(e.currentTarget);
  ConfigureStore.set($ele.attr('name'), $ele.prop('checked'));

  if($ele.attr('name') == 'fixed_port') {
    portNoDisableCheck();
  }
}

$('#btnSave').on('click', ()=> {
  ConfigureStore.save();
});

function portNoDisableCheck() {
  $('#portNo').prop('disabled', !ConfigureStore.get('fixed_port', false));
}

/* load the values initially */
ConfigureStore.keys().map((keyname) => {
  let $ele = $(`*[name="${keyname}"]`);
  let value = ConfigureStore.get(keyname);

  switch ($ele.attr('type')) {
  case 'checkbox':
    $ele.on('change', onCheckChange)
      .prop('checked', value);
    break;
  default:
    $ele.on('change keyup', onTextChange)
      .val(value);
    break;
  }
});

portNoDisableCheck();