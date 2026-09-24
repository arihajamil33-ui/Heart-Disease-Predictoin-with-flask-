document.addEventListener('DOMContentLoaded', function () {
  var form = document.getElementById('registerForm');
  if (!form) return;
  var username = document.getElementById('username');
  var fullname = document.getElementById('fullname');
  var email    = document.getElementById('email');
  var password = document.getElementById('password');
  var confirm  = document.getElementById('confirm_password');
  var meter    = document.getElementById('pwMeter');
  var meterBar = document.getElementById('pwMeterBar');
  var meterTxt = document.getElementById('pwMeterText');
  var submitBtn = document.getElementById('registerBtn');
  var roleSelect     = document.getElementById('register_as');
  var doctorFields   = document.getElementById('doctorFields');
  var specialization = document.getElementById('specialization');
  var licenseNo      = document.getElementById('license_no');
  function setError(input, message) {
    var box = document.querySelector('[data-error-for="' + input.id + '"]');
    if (message) {
      input.classList.add('invalid');
      if (box) { box.textContent = '⚠ ' + message; box.classList.add('show'); }
      return false;
    }
    input.classList.remove('invalid');
    if (box) { box.textContent = ''; box.classList.remove('show'); }
    return true;
  }
  function isDoctor() {
    return roleSelect && roleSelect.value === 'Doctor';
  }
  function syncDoctorFields() {
    var doctor = isDoctor();
    if (doctorFields) doctorFields.style.display = doctor ? 'block' : 'none';
    if (specialization) specialization.required = doctor;
    if (licenseNo) licenseNo.required = doctor;
    if (!doctor) {
      if (specialization) setError(specialization, null);
      if (licenseNo) setError(licenseNo, null);
    }
  }
  function checkUsername() {
    var v = username.value.trim();
    if (!v)                       return setError(username, 'A username is required.');
    if (v.length < 3)             return setError(username, 'At least 3 characters.');
    if (v.length > 20)            return setError(username, 'No more than 20 characters.');
    if (!/^[A-Za-z0-9_]+$/.test(v))
      return setError(username, 'Letters, numbers and underscores only.');
    if (!/^[A-Za-z]/.test(v))     return setError(username, 'Must start with a letter.');
    return setError(username, null);
  }
  function checkFullname() {
    var v = fullname.value.trim();
    if (!v)            return setError(fullname, 'Your full name is required.');
    if (v.length < 2)  return setError(fullname, 'At least 2 characters.');
    if (v.length > 60) return setError(fullname, 'No more than 60 characters.');
    if (!/^[A-Za-z .'\-]+$/.test(v))
      return setError(fullname, 'Letters, spaces, hyphens and apostrophes only.');
    return setError(fullname, null);
  }
  function checkEmail() {
    var v = email.value.trim();
    if (!v) return setError(email, 'An email address is required.');
    if (!/^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$/.test(v))
      return setError(email, 'Enter a valid address, e.g. name@example.com.');
    return setError(email, null);
  }
  function checkPassword() {
    var v = password.value;
    if (v.length < 8)          return setError(password, 'At least 8 characters.');
    if (v.length > 72)         return setError(password, 'No more than 72 characters.');
    if (!/[A-Za-z]/.test(v))   return setError(password, 'Must include at least one letter.');
    if (!/\d/.test(v))         return setError(password, 'Must include at least one number.');
    if (/\s/.test(v))          return setError(password, 'Cannot contain spaces.');
    if (username.value && v.toLowerCase() === username.value.trim().toLowerCase())
      return setError(password, 'Cannot be the same as your username.');
    return setError(password, null);
  }
  function checkConfirm() {
    if (!confirm.value)                  return setError(confirm, 'Please re-enter the password.');
    if (confirm.value !== password.value) return setError(confirm, 'The two passwords do not match.');
    return setError(confirm, null);
  }
  function checkSpecialization() {
    if (!isDoctor()) return setError(specialization, null);
    var v = specialization.value.trim();
    if (!v)          return setError(specialization, 'Your specialization is required.');
    if (v.length < 2)  return setError(specialization, 'At least 2 characters.');
    if (v.length > 80) return setError(specialization, 'No more than 80 characters.');
    return setError(specialization, null);
  }
  function checkLicense() {
    if (!isDoctor()) return setError(licenseNo, null);
    var v = licenseNo.value.trim();
    if (!v) return setError(licenseNo, 'Your medical license number is required.');
    if (!/^[A-Za-z0-9\-\/]{3,40}$/.test(v))
      return setError(licenseNo, '3-40 characters: letters, numbers, - or /.');
    return setError(licenseNo, null);
  }
  function updateMeter() {
    var v = password.value;
    if (!v) { meter.style.display = 'none'; return; }
    meter.style.display = 'block';
    var score = 0;
    if (v.length >= 8)  score++;
    if (v.length >= 12) score++;
    if (/[A-Za-z]/.test(v) && /\d/.test(v)) score++;
    if (/[A-Z]/.test(v) && /[a-z]/.test(v)) score++;
    if (/[^A-Za-z0-9]/.test(v)) score++;
    var levels = [
      { pct: 20,  colour: '#ef4444', label: '😟 Very weak' },
      { pct: 40,  colour: '#f97316', label: '😕 Weak' },
      { pct: 60,  colour: '#f59e0b', label: '😐 Fair' },
      { pct: 80,  colour: '#84cc16', label: '🙂 Good' },
      { pct: 100, colour: '#10b981', label: '😄 Strong' }
    ];
    var level = levels[Math.min(Math.max(score - 1, 0), 4)];
    meterBar.style.width = level.pct + '%';
    meterBar.style.background = level.colour;
    meterTxt.textContent = level.label;
    meterTxt.style.color = level.colour;
  }
  username.addEventListener('blur',  checkUsername);
  fullname.addEventListener('blur',  checkFullname);
  email.addEventListener('blur',     checkEmail);
  password.addEventListener('input', function () { updateMeter(); });
  password.addEventListener('blur',  checkPassword);
  confirm.addEventListener('input',  function () { if (confirm.value) checkConfirm(); });
  confirm.addEventListener('blur',   checkConfirm);
  if (roleSelect) roleSelect.addEventListener('change', syncDoctorFields);
  if (specialization) specialization.addEventListener('blur', checkSpecialization);
  if (licenseNo) licenseNo.addEventListener('blur', checkLicense);
  syncDoctorFields();     // re-selecting a submitted form keeps state right
  form.addEventListener('submit', function (e) {
    var ok = checkUsername();
    ok = checkFullname() && ok;
    ok = checkEmail() && ok;
    ok = checkPassword() && ok;
    ok = checkConfirm() && ok;
    if (isDoctor()) {
      ok = checkSpecialization() && ok;
      ok = checkLicense() && ok;
    }
    if (!ok) {
      e.preventDefault();
      var firstBad = form.querySelector('.invalid');
      if (firstBad) { firstBad.scrollIntoView({behavior:'smooth', block:'center'}); firstBad.focus(); }
      return false;
    }
    if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = 'Creating account…'; }
  });
});
