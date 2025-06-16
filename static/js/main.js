import { renderDisplay } from './display_mirror.js';
import { loadPlugins } from './plugin_loader.js';

window.showTab = function(tab) {
  document.querySelectorAll('.tab').forEach(el => el.style.display = 'none');
  document.getElementById(tab).style.display = '';
};

window.onload = () => {
  showTab('display');
  renderDisplay('display-canvas');
  loadPlugins('plugin-list');
};