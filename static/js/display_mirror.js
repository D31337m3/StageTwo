export async function renderDisplay(canvasId) {
  const res = await fetch('/api/display');
  const data = await res.json();
  const canvas = document.getElementById(canvasId);
  canvas.width = data.width;
  canvas.height = data.height;
  const ctx = canvas.getContext('2d');
  // RGBA flat array
  const imgData = ctx.createImageData(data.width, data.height);
  for (let i = 0; i < data.pixels.length; i++) {
    imgData.data[i] = data.pixels[i];
  }
  ctx.putImageData(imgData, 0, 0);
}