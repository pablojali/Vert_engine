// "Get Your VTL Analysis" form (/analysis/): client-side validation +
// async submit to the Cloudflare Pages Function at /api/analysis-request,
// which is the only thing that ever sees the real GPX bytes, the
// Turnstile secret, or the email API key - none of that lives here.
// No-ops entirely on any page without the form (every other page).

(function () {
  var MAX_GPX_BYTES = 8 * 1024 * 1024; // keep in sync with functions/api/analysis-request.js
  var EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

  var form = document.getElementById("analysis-form");
  if (!form) return;

  var errorBox = document.getElementById("analysis-form-error");
  var successBox = document.getElementById("analysis-success");
  var submitBtn = document.getElementById("analysis-submit-btn");

  function showError(message) {
    if (!errorBox) return;
    errorBox.textContent = message;
    errorBox.hidden = false;
  }

  function clearError() {
    if (!errorBox) return;
    errorBox.hidden = true;
    errorBox.textContent = "";
  }

  function validate() {
    var required = ["name", "email", "race", "distance", "race_date"];
    for (var i = 0; i < required.length; i++) {
      var field = form.elements[required[i]];
      if (!field || !field.value.trim()) return form.dataset.errorRequired;
    }
    var email = form.elements["email"].value.trim();
    if (!EMAIL_RE.test(email)) return form.dataset.errorEmail;

    var gpxInput = form.elements["gpx"];
    var gpxFile = gpxInput && gpxInput.files && gpxInput.files[0];
    if (!gpxFile) return form.dataset.errorRequired;
    if (!/\.gpx$/i.test(gpxFile.name)) return form.dataset.errorGpxType;
    if (gpxFile.size > MAX_GPX_BYTES) return form.dataset.errorGpxSize;

    return null;
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    clearError();

    var validationError = validate();
    if (validationError) {
      showError(validationError);
      return;
    }

    submitBtn.disabled = true;
    submitBtn.textContent = form.dataset.submittingLabel || submitBtn.textContent;

    fetch("/api/analysis-request", { method: "POST", body: new FormData(form) })
      .then(function (res) {
        return res.json().catch(function () { return {}; }).then(function (data) {
          return { ok: res.ok, data: data };
        });
      })
      .then(function (result) {
        if (result.ok && result.data && result.data.success) {
          form.hidden = true;
          if (successBox) successBox.hidden = false;
          return;
        }
        var code = result.data && result.data.error;
        var message =
          (code === "gpx_invalid" && form.dataset.errorGpxType) ||
          (code === "gpx_too_large" && form.dataset.errorGpxSize) ||
          (code === "invalid_input" && form.dataset.errorRequired) ||
          form.dataset.errorGeneric;
        // TEMP_DEBUG: surfaces the server's `debug` field (see
        // functions/api/analysis-request.js) while setting up Resend -
        // remove this "+ debug" once real submissions work end to end.
        if (result.data && result.data.debug) {
          message += " (debug: " + result.data.debug + ")";
        }
        showError(message);
      })
      .catch(function () {
        showError(form.dataset.errorGeneric);
      })
      .finally(function () {
        submitBtn.disabled = false;
        submitBtn.textContent = form.dataset.submitLabel || submitBtn.textContent;
      });
  });
})();
