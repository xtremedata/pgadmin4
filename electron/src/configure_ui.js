window.ipcEvent = window.get_event_handle();

var $ = window.$ = window.jQuery = window.require_package('jquery');
window.Bootstrap = window.require_package('bootstrap');
const {EVENTS} = window.require_package('./constants');

var state = {};

function setState(key, value) {
  state[key] = value;
}

function onTextChange(e) {
  let $ele = $(e.currentTarget);
  setState($ele.attr('data-name'), $ele.val());
}

function onCheckChange(e) {
  let $ele = $(e.currentTarget);
  setState($ele.attr('data-name'), $ele.prop('checked'));

  if($ele.attr('data-name') == 'fixed_port') {
    portNoDisableCheck();
  }
}

function portNoDisableCheck() {
  if(state.fixed_port === undefined) {
    state.fixed_port = false;
  }
  $('#portNo').prop('disabled', state.fixed_port);
}

function setStatus(msg) {
  $('.status-text').html(msg);
}

$('#btnSave').on('click', ()=> {
  $('#btnSave').prop('disabled', true);
  window.ipcEvent.send(EVENTS.SAVE_CONFIG, state);
});

window.ipcEvent.on(EVENTS.SAVE_DATA_SUCCESS, ()=>{
  $('#btnSave').prop('disabled', false);
  setStatus('Success !!');
});

window.ipcEvent.on(EVENTS.SAVE_DATA_FAILED, ()=>{
  $('#btnSave').prop('disabled', false);
  setStatus('Failed !!');
});

window.ipcEvent.on(EVENTS.LOAD_CONFIG, (event, data)=>{
  state = data;
  Object.keys(state).map((keyname) => {
    let $ele = $(`*[data-name="${keyname}"]`);
    let value = state[keyname];

    switch ($ele.attr('type')) {
    case 'checkbox':
      $ele.prop('checked', value);
      break;
    default:
      $ele.val(value);
      break;
    }
  });

  portNoDisableCheck();
  setStatus('');
  $('#btnSave').prop('disabled', false);
});

$('*[data-name]').each(function() {
  let $ele = $(this);
  switch ($ele.attr('type')) {
  case 'checkbox':
    $ele.on('change', onCheckChange);
    break;
  default:
    $ele.on('change keyup', onTextChange);
    break;
  }
});

setStatus('Loading config...');
window.ipcEvent.send(EVENTS.LOAD_CONFIG);