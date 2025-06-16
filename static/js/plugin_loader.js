export async function loadPlugins(listId) {
  const res = await fetch('/api/plugins');
  const plugins = await res.json();
  const ul = document.getElementById(listId);
  ul.innerHTML = '';
  plugins.forEach(name => {
    const li = document.createElement('li');
    li.textContent = name;
    ul.appendChild(li);
  });
}