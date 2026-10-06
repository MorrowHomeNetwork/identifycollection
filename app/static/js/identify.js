/*
  On the "tell the museum" form: show only the questions that fit the kind of
  evidence chosen. With scripts switched off, every question simply stays
  visible, and the form still works.
*/
(function () {
  "use strict";
  var form = document.getElementById("identify-form");
  if (!form) { return; }
  var sections = form.querySelectorAll("[data-evidence]");
  function refresh() {
    var chosen = form.querySelector('input[name="evidence_kind"]:checked');
    sections.forEach(function (section) {
      section.hidden = !chosen || section.dataset.evidence.split(" ").indexOf(chosen.value) === -1;
    });
  }
  form.querySelectorAll('input[name="evidence_kind"]').forEach(function (radio) {
    radio.addEventListener("change", refresh);
  });
  refresh();
})();
