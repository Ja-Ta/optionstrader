/* Chart bootstrapping: fragments embed uPlot payloads as
   <div class="chart" data-chart="price|cd|equity"><script type="application/json">…</script></div>
   and this initializer draws them on page load and after every htmx swap. */
(function () {
  "use strict";

  function hlinePlugin(hlines) {
    return {
      hooks: {
        draw: function (u) {
          var ctx = u.ctx;
          ctx.save();
          hlines.forEach(function (h) {
            var y = u.valToPos(h.y, "y", true);
            if (y < u.bbox.top || y > u.bbox.top + u.bbox.height) return;
            ctx.strokeStyle = h.role === "support" ? "#1a7f37" : "#cf222e";
            ctx.setLineDash([6, 5]);
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(u.bbox.left, y);
            ctx.lineTo(u.bbox.left + u.bbox.width, y);
            ctx.stroke();
          });
          ctx.restore();
        },
      },
    };
  }

  var PALETTE = ["#1f6feb", "#9a6700", "#1a7f37", "#cf222e", "#8250df"];

  function draw(el) {
    if (el.dataset.drawn) return;
    var payloadEl = el.querySelector('script[type="application/json"]');
    if (!payloadEl || typeof uPlot === "undefined") return;
    var p = JSON.parse(payloadEl.textContent);
    var data = [p.x].concat(p.series.map(function (s) { return s.values; }));
    var series = [{}].concat(
      p.series.map(function (s, i) {
        return {
          label: s.label,
          stroke: PALETTE[i % PALETTE.length],
          width: 1.5,
          scale: s.scale || "y",
        };
      })
    );
    var opts = {
      width: Math.min(el.clientWidth || 900, 1000),
      height: 280,
      series: series,
      plugins: p.hlines && p.hlines.length ? [hlinePlugin(p.hlines)] : [],
      axes: [{}, {}],
      scales: { x: { time: true } },
    };
    if (p.series.some(function (s) { return s.scale === "cd"; })) {
      opts.axes.push({ scale: "cd", side: 1 });
      opts.scales.cd = { range: [0, 11] };
    }
    new uPlot(opts, data, el);
    el.dataset.drawn = "1";
  }

  function drawAll(root) {
    (root || document).querySelectorAll("div[data-chart]").forEach(draw);
  }

  document.addEventListener("DOMContentLoaded", function () { drawAll(); });
  document.addEventListener("htmx:afterSwap", function (e) { drawAll(e.target); });

  /* Record page: open-shorts picker fills the buyback/expired/assigned form. */
  window.fillShort = function (prefix, kind, strike, expiry) {
    var set = function (suffix, value) {
      var el = document.getElementById(prefix + "-" + suffix);
      if (el) el.value = value;
    };
    set("kind", kind);
    set("strike", strike);
    set("expiry", expiry);
  };
})();
