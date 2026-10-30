import { LAND_MASK, POINTS } from "./globe-mask.js";

// Trading hubs, as [latitude, longitude]. Decorative only: arcs are not real order flow.
const HUBS = {
  mumbai: [19.08, 72.88], bengaluru: [12.97, 77.59], newYork: [40.71, -74.01], toronto: [43.65, -79.38],
  sanFrancisco: [37.77, -122.42], mexicoCity: [19.43, -99.13], saoPaulo: [-23.55, -46.63],
  buenosAires: [-34.6, -58.38], london: [51.51, -0.13], amsterdam: [52.37, 4.9], frankfurt: [50.11, 8.68],
  madrid: [40.42, -3.7], lagos: [6.52, 3.38], nairobi: [-1.29, 36.82], johannesburg: [-26.2, 28.05],
  cairo: [30.04, 31.24], dubai: [25.2, 55.27], riyadh: [24.71, 46.68], singapore: [1.35, 103.82],
  hongKong: [22.32, 114.17], tokyo: [35.68, 139.69], seoul: [37.57, 126.98], sydney: [-33.87, 151.21],
};
const ROUTES = [
  ["mumbai", "dubai"], ["mumbai", "singapore"], ["mumbai", "london"], ["bengaluru", "frankfurt"], ["lagos", "london"],
  ["lagos", "nairobi"], ["johannesburg", "nairobi"], ["johannesburg", "dubai"], ["cairo", "riyadh"], ["dubai", "london"],
  ["madrid", "saoPaulo"], ["madrid", "lagos"], ["amsterdam", "newYork"], ["london", "newYork"], ["newYork", "saoPaulo"],
  ["toronto", "mexicoCity"], ["sanFrancisco", "tokyo"], ["buenosAires", "saoPaulo"], ["singapore", "sydney"],
  ["singapore", "hongKong"], ["hongKong", "tokyo"], ["seoul", "singapore"], ["frankfurt", "dubai"], ["nairobi", "mumbai"],
];

const TILT = -0.66;
const SPIN_PER_MS = 0.000055;
const START_LONGITUDE = 38;
const FRAME_MS = 30;
const ACTIVE_ARCS = 9;
const ARC_MS = 3200;
const ARC_STEPS = 34;
const TAIL = 0.34;
const SHADES = 14;

const canvas = document.getElementById("globe-canvas");
const context = canvas?.getContext("2d");

function vector([lat, lon]) {
  const phi = (lat * Math.PI) / 180;
  const theta = (lon * Math.PI) / 180;
  return [Math.cos(phi) * Math.sin(theta), Math.sin(phi), Math.cos(phi) * Math.cos(theta)];
}

function landPoints() {
  const bytes = Uint8Array.from(atob(LAND_MASK), (char) => char.charCodeAt(0));
  const golden = Math.PI * (3 - Math.sqrt(5));
  const points = [];
  for (let i = 0; i < POINTS; i += 1) {
    if (!(bytes[i >> 3] & (1 << (i & 7)))) continue;
    const y = 1 - (2 * i + 1) / POINTS;
    const radius = Math.sqrt(1 - y * y);
    const angle = i * golden;
    points.push(radius * Math.sin(angle), y, radius * Math.cos(angle));
  }
  return new Float32Array(points);
}

function arcPath(from, to) {
  const angle = Math.acos(Math.min(1, from[0] * to[0] + from[1] * to[1] + from[2] * to[2]));
  const path = [];
  for (let step = 0; step <= ARC_STEPS; step += 1) {
    const t = step / ARC_STEPS;
    const a = Math.sin((1 - t) * angle) / Math.sin(angle);
    const b = Math.sin(t * angle) / Math.sin(angle);
    const lift = 1 + Math.sin(t * Math.PI) * angle * 0.07;
    path.push([(a * from[0] + b * to[0]) * lift, (a * from[1] + b * to[1]) * lift, (a * from[2] + b * to[2]) * lift]);
  }
  return path;
}

// Dots run from the sun-struck limb (bright, warm) to the shaded face (dim, neutral).
function shadeRamp() {
  const warm = [255, 176, 112];
  const cold = [118, 108, 104];
  return Array.from({ length: SHADES }, (_, index) => {
    const t = index / (SHADES - 1);
    const mix = (channel) => Math.round(cold[channel] + (warm[channel] - cold[channel]) * t ** 1.3);
    return `rgba(${mix(0)},${mix(1)},${mix(2)},${(0.12 + 0.88 * t ** 1.2).toFixed(3)})`;
  });
}

function start() {
  const land = landPoints();
  const ramp = shadeRamp();
  const hubs = Object.fromEntries(Object.entries(HUBS).map(([name, place]) => [name, vector(place)]));
  const hubList = Object.values(hubs);
  const routes = ROUTES.map(([from, to]) => arcPath(hubs[from], hubs[to]));
  const arcs = Array.from({ length: ACTIVE_ARCS }, (_, index) => ({
    path: routes[Math.floor(Math.random() * routes.length)],
    born: -index * (ARC_MS / ACTIVE_ARCS),
  }));
  const sinTilt = Math.sin(TILT);
  const cosTilt = Math.cos(TILT);
  const reduced = matchMedia("(prefers-reduced-motion: reduce)");
  const shadePaths = Array.from({ length: SHADES }, () => []);
  let width = 0;
  let height = 0;
  let radius = 0;
  let centerX = 0;
  let centerY = 0;
  let scale = 1;
  let dotScale = 1;
  let visible = true;
  let frame = 0;
  let lastDraw = 0;
  let spin = (-START_LONGITUDE * Math.PI) / 180;
  let previous = 0;

  function project(x, y, z, sinSpin, cosSpin) {
    const spunX = x * cosSpin + z * sinSpin;
    const spunZ = -x * sinSpin + z * cosSpin;
    return [
      centerX + spunX * radius,
      centerY - (y * cosTilt - spunZ * sinTilt) * radius,
      y * sinTilt + spunZ * cosTilt,
    ];
  }

  // Markers melt away down the disc so nothing floats past the lit cap.
  function horizonFade(screenY) {
    const up = (centerY - screenY) / radius;
    return Math.min(1, Math.max(0, (up - 0.34) / 0.22));
  }

  function drawLand(sinSpin, cosSpin) {
    for (const path of shadePaths) path.length = 0;
    for (let index = 0; index < land.length; index += 3) {
      const x = land[index];
      const y = land[index + 1];
      const z = land[index + 2];
      const spunX = x * cosSpin + z * sinSpin;
      const spunZ = -x * sinSpin + z * cosSpin;
      const depth = y * sinTilt + spunZ * cosTilt;
      if (depth <= 0.015) continue;
      const up = y * cosTilt - spunZ * sinTilt;
      const screenY = centerY - up * radius;
      if (screenY > height) continue;
      const screenX = centerX + spunX * radius;
      if (screenX < -4 || screenX > width + 4) continue;
      // Light comes from just behind the top of the disc, so the limb catches it first.
      const lit = Math.max(0, up * 0.92 + depth * 0.22 - 0.08) ** 2.3 + (1 - depth) ** 3 * Math.max(0, up) * 0.5;
      const shade = Math.min(SHADES - 1, Math.floor(lit * SHADES));
      const size = dotScale * (0.95 + depth * 0.95) * (1 + lit * 0.35);
      shadePaths[shade].push(screenX, screenY, size);
    }
    for (let shade = 0; shade < SHADES; shade += 1) {
      const path = shadePaths[shade];
      if (!path.length) continue;
      context.fillStyle = ramp[shade];
      context.beginPath();
      for (let index = 0; index < path.length; index += 3) {
        context.rect(path[index], path[index + 1], path[index + 2], path[index + 2]);
      }
      context.fill();
    }
  }

  function drawHubs(sinSpin, cosSpin, now) {
    context.fillStyle = "#ffd9b8";
    for (const hub of hubList) {
      const [x, y, depth] = project(hub[0], hub[1], hub[2], sinSpin, cosSpin);
      const fade = Math.min(1, depth * 3) * horizonFade(y);
      if (depth < 0.06 || fade <= 0) continue;
      context.globalAlpha = fade;
      context.beginPath();
      context.arc(x, y, 2.1, 0, Math.PI * 2);
      context.fill();
      const pulse = ((now / 2600 + hub[0] * 3) % 1 + 1) % 1;
      context.globalAlpha = fade * (1 - pulse) * 0.5;
      context.strokeStyle = "#ffb071";
      context.lineWidth = 1;
      context.beginPath();
      context.arc(x, y, 2 + pulse * 13, 0, Math.PI * 2);
      context.stroke();
    }
    context.globalAlpha = 1;
  }

  function drawArcs(sinSpin, cosSpin, now) {
    context.lineCap = "round";
    for (const arc of arcs) {
      let progress = (now - arc.born) / ARC_MS;
      if (progress >= 1 + TAIL) {
        arc.path = routes[Math.floor(Math.random() * routes.length)];
        arc.born = now;
        progress = 0;
      }
      if (progress <= 0) continue;
      const head = Math.min(1, progress);
      const tail = Math.max(0, progress - TAIL);
      const last = Math.floor(head * ARC_STEPS);
      let previousPoint = null;
      for (let step = Math.floor(tail * ARC_STEPS); step <= last; step += 1) {
        const [x, y, z] = arc.path[step];
        const point = project(x, y, z, sinSpin, cosSpin);
        if (previousPoint && point[2] > 0 && previousPoint[2] > 0) {
          const fade = (step / ARC_STEPS - tail) / Math.max(0.001, head - tail);
          const alpha = fade * 0.95 * horizonFade(point[1]);
          context.strokeStyle = `rgba(255,${Math.round(150 + 70 * fade)},${Math.round(90 + 90 * fade)},${alpha.toFixed(3)})`;
          context.lineWidth = 0.6 + fade * 1.1;
          context.beginPath();
          context.moveTo(previousPoint[0], previousPoint[1]);
          context.lineTo(point[0], point[1]);
          context.stroke();
        }
        previousPoint = point;
      }
      if (progress < 1 && previousPoint && previousPoint[2] > 0 && horizonFade(previousPoint[1]) > 0) {
        context.fillStyle = "#fff1e2";
        context.beginPath();
        context.arc(previousPoint[0], previousPoint[1], 1.8, 0, Math.PI * 2);
        context.fill();
      }
    }
  }

  function draw(now) {
    const sinSpin = Math.sin(spin);
    const cosSpin = Math.cos(spin);
    context.setTransform(scale, 0, 0, scale, 0, 0);
    context.clearRect(0, 0, width, height);
    drawLand(sinSpin, cosSpin);
    if (!reduced.matches) drawArcs(sinSpin, cosSpin, now);
    drawHubs(sinSpin, cosSpin, reduced.matches ? 0 : now);
  }

  function tick(now) {
    frame = requestAnimationFrame(tick);
    if (now - lastDraw < FRAME_MS) return;
    spin += Math.min(100, now - (previous || now)) * SPIN_PER_MS;
    previous = now;
    lastDraw = now;
    draw(now);
  }

  function run() {
    cancelAnimationFrame(frame);
    previous = 0;
    if (visible && !reduced.matches && !document.hidden) frame = requestAnimationFrame(tick);
    else draw(performance.now());
  }

  // The stylesheet owns the geometry: the canvas fills .globe, a circle that overflows its parent.
  function resize() {
    const box = canvas.parentElement.getBoundingClientRect();
    const clip = canvas.closest(".sky").getBoundingClientRect();
    radius = box.width / 2;
    dotScale = Math.min(1.7, Math.max(1, radius / 400));
    width = clip.width;
    height = clip.bottom - box.top;
    centerX = width / 2;
    centerY = radius;
    scale = Math.min(devicePixelRatio, 2);
    canvas.width = Math.round(width * scale);
    canvas.height = Math.round(height * scale);
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    canvas.style.left = `${box.width / 2 - width / 2}px`;
    draw(performance.now());
  }

  new ResizeObserver(resize).observe(canvas.closest(".sky"));
  new IntersectionObserver(([entry]) => {
    visible = entry.isIntersecting;
    run();
  }).observe(canvas.closest(".sky"));
  document.addEventListener("visibilitychange", run);
  reduced.addEventListener("change", run);
  resize();
  run();
}

if (context) start();
