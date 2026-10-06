/*
  Adding photographs: sends the chosen scans to the app one at a time and
  reports progress, so a folder of several hundred large files cannot time
  out or leave you wondering. With scripts switched off, the form still
  sends the chosen files in the ordinary way.
*/
(function () {
  "use strict";
  var form = document.getElementById("upload-form");
  if (!form || !window.fetch || !window.FormData) { return; }

  var fileInput = document.getElementById("upload-files");
  var folderInput = document.getElementById("upload-folder");
  var folderField = document.getElementById("folder-field");
  var progress = document.getElementById("upload-progress");
  var PICTURE = /\.(jpe?g|png|tiff?|webp|bmp|gif)$/i;

  if (folderField && "webkitdirectory" in folderInput) { folderField.hidden = false; }

  function chosenFiles() {
    var all = Array.prototype.slice.call(fileInput.files).concat(Array.prototype.slice.call(folderInput.files || []));
    return all.filter(function (file) { return PICTURE.test(file.name); });
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    var files = chosenFiles();
    if (!files.length) {
      progress.hidden = false;
      progress.textContent = "Choose some picture files first.";
      return;
    }
    var token = form.querySelector('input[name="csrfmiddlewaretoken"]').value;
    var button = form.querySelector("button");
    var added = 0, already = 0, failed = [];
    button.disabled = true;
    progress.hidden = false;

    function finish() {
      button.disabled = false;
      var summary = "Finished: " + added + " added";
      if (already) { summary += ", " + already + " already here"; }
      if (!failed.length) { window.location.reload(); return; }
      progress.textContent = summary + ", " + failed.length + " could not be read:";
      var list = document.createElement("ul");
      failed.forEach(function (name) { var item = document.createElement("li"); item.textContent = name; list.appendChild(item); });
      progress.appendChild(list);
      var again = document.createElement("a");
      again.href = window.location.href;
      again.textContent = "Show the photographs";
      progress.appendChild(again);
    }

    function sendNext(index) {
      if (index >= files.length) { finish(); return; }
      var file = files[index];
      progress.textContent = "Adding " + (index + 1) + " of " + files.length + ": " + file.name;
      var body = new FormData();
      body.append("file", file, file.name);
      fetch(form.action, {
        method: "POST",
        body: body,
        credentials: "same-origin",
        headers: { "X-CSRFToken": token, "X-Requested-With": "fetch" }
      }).then(function (response) {
        if (!response.ok) { throw new Error("refused"); }
        return response.json();
      }).then(function (answer) {
        var result = answer.results[0];
        if (!result.ok) { failed.push(file.name); }
        else if (result.duplicate) { already += 1; }
        else { added += 1; }
      }).catch(function () {
        failed.push(file.name);
      }).then(function () { sendNext(index + 1); });
    }
    sendNext(0);
  });
})();
