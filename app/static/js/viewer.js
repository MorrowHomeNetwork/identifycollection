/*
  The zoomable photograph, and the "mark a person" box.

  The zooming is done by OpenSeadragon (stored in static/vendor, not loaded
  from the internet). This file adds: the three zoom buttons, the boxes for
  people already named, and letting a visitor drag a box around a face.

  A box is stored as four fractions of the picture (left, top, width,
  height, each between 0 and 1), so it means the same thing at any size.
*/
(function () {
  "use strict";

  var holder = document.getElementById("viewer");
  if (!holder || typeof OpenSeadragon === "undefined") { return; }

  var aspect = Number(holder.dataset.height) / Number(holder.dataset.width);
  var boxes = [];
  var boxData = document.getElementById("boxes");
  if (boxData) {
    try { boxes = JSON.parse(boxData.textContent); } catch (problem) { boxes = []; }
  }

  holder.textContent = ""; // remove the plain picture shown when scripts are off
  holder.style.aspectRatio = holder.dataset.width + " / " + holder.dataset.height; // the frame takes the picture's shape

  var viewer = OpenSeadragon({
    element: holder,
    tileSources: { type: "image", url: holder.dataset.image },
    drawer: "canvas",              // works on old laptops that lack modern graphics support
    showNavigationControl: false,  // we provide our own plainly worded buttons
    maxZoomPixelRatio: 4,
    visibilityRatio: 1,
    constrainDuringPan: true,
    gestureSettingsMouse: { clickToZoom: false },
    gestureSettingsTouch: { clickToZoom: false }
  });
  window.identifyViewer = viewer; // lets the automated tests reach it

  document.querySelectorAll("[data-zoom]").forEach(function (button) {
    button.addEventListener("click", function () {
      var what = button.dataset.zoom;
      if (what === "home") { viewer.viewport.goHome(); return; }
      viewer.viewport.zoomBy(what === "in" ? 1.6 : 1 / 1.6);
      viewer.viewport.applyConstraints();
    });
  });

  // OpenSeadragon measures in "viewport" units: the picture is 1 wide and
  // `aspect` tall. These two functions convert to and from our fractions.
  function toRect(box) {
    return new OpenSeadragon.Rect(box.x, box.y * aspect, box.w, box.h * aspect);
  }
  function toBox(rect) {
    return { x: rect.x, y: rect.y / aspect, w: rect.width, h: rect.height / aspect };
  }

  function drawBox(box) {
    var frame = document.createElement("div");
    frame.className = "box box-" + (box.kind || "named");
    if (box.label) {
      var tag = document.createElement("span");
      tag.className = "box-tag";
      tag.textContent = box.label;
      frame.appendChild(tag);
    }
    viewer.addOverlay({ element: frame, location: toRect(box) });
    return frame;
  }

  // ----- marking -----

  var markButton = document.getElementById("mark-button");
  var statusLine = document.getElementById("mark-status");
  var inputs = {
    x: document.getElementById("id_box_x"), y: document.getElementById("id_box_y"),
    w: document.getElementById("id_box_w"), h: document.getElementById("id_box_h")
  };
  var canMark = Boolean(markButton && inputs.x && inputs.y && inputs.w && inputs.h);
  var marking = false;
  var startPoint = null;
  var draftRect = null;
  var draftFrame = null;

  function say(text) { if (statusLine) { statusLine.textContent = text; } }
  function hasMark() { return canMark && inputs.x.value !== "" && inputs.w.value !== ""; }

  function showDraft(rect) {
    if (!draftFrame) {
      draftFrame = document.createElement("div");
      draftFrame.className = "box box-draft";
      viewer.addOverlay({ element: draftFrame, location: rect });
    } else {
      viewer.updateOverlay(draftFrame, rect);
    }
  }

  function clearDraft() {
    if (draftFrame) { viewer.removeOverlay(draftFrame); draftFrame = null; }
    ["x", "y", "w", "h"].forEach(function (key) { inputs[key].value = ""; });
  }

  function setMarking(on) {
    marking = on;
    startPoint = null;
    holder.classList.toggle("is-marking", on);
    markButton.setAttribute("aria-pressed", on ? "true" : "false");
    markButton.textContent = on ? "Cancel marking" : (hasMark() ? "Mark again" : "Mark a person");
    if (on) { say("Now drag a box around the person's face."); }
  }

  function pointAt(event) {
    var point = viewer.viewport.pointFromPixel(event.position);
    return new OpenSeadragon.Point(Math.min(Math.max(point.x, 0), 1), Math.min(Math.max(point.y, 0), aspect));
  }

  if (canMark) {
    markButton.addEventListener("click", function () {
      if (!marking) { clearDraft(); }
      setMarking(!marking);
      if (!marking) { say(""); }
    });

    viewer.addHandler("canvas-press", function (event) {
      if (marking) { startPoint = pointAt(event); draftRect = null; }
    });

    viewer.addHandler("canvas-drag", function (event) {
      if (!marking || !startPoint) { return; }
      event.preventDefaultAction = true; // do not slide the picture while a box is being drawn
      var now = pointAt(event);
      draftRect = new OpenSeadragon.Rect(
        Math.min(startPoint.x, now.x), Math.min(startPoint.y, now.y),
        Math.abs(now.x - startPoint.x), Math.abs(now.y - startPoint.y)
      );
      showDraft(draftRect);
    });

    viewer.addHandler("canvas-drag-end", function () {
      if (!marking || !startPoint) { return; }
      var box = draftRect ? toBox(draftRect) : null;
      if (!box || box.w < 0.004 || box.h < 0.004) {
        clearDraft();
        startPoint = null;
        say("That was too small to see. Press and drag to draw the box.");
        return;
      }
      ["x", "y", "w", "h"].forEach(function (key) { inputs[key].value = box[key].toFixed(5); });
      setMarking(false);
      say("Marked. Now tell the museum who it is, below.");
    });

    viewer.addHandler("canvas-click", function (event) {
      if (marking) { event.preventDefaultAction = true; }
    });
  }

  viewer.addHandler("open", function () {
    boxes.forEach(drawBox);
    if (hasMark()) { // the form came back with a question; keep the visitor's mark on screen
      showDraft(toRect({
        x: Number(inputs.x.value), y: Number(inputs.y.value),
        w: Number(inputs.w.value), h: Number(inputs.h.value)
      }));
      markButton.textContent = "Mark again";
      say("Your mark is still here.");
    }
    holder.dataset.ready = "yes";
  });
})();
