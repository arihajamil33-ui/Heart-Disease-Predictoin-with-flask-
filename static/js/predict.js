document.addEventListener('DOMContentLoaded', function () {
  var form = document.getElementById('predictForm');
  if (!form) return;
  var heightEl  = document.getElementById('height');
  var weightEl  = document.getElementById('weight');
  var apHiEl    = document.getElementById('ap_hi');
  var apLoEl    = document.getElementById('ap_lo');
  var bmiValue  = document.getElementById('bmiValue');
  var bmiCat    = document.getElementById('bmiCategory');
  var bmiBox    = document.getElementById('bmiReadout');
  var bpWarning = document.getElementById('bpWarning');
  var submitBtn = document.getElementById('submitBtn');
  var COLOURS = {
    blue:  '#3b82f6',
    green: '#10b981',
    amber: '#f59e0b',
    red:   '#ef4444',
    grey:  '#9ca3af'
  };
  function bmiInfo(bmi) {
    if (bmi < 18.5) return { label: 'Underweight',   colour: COLOURS.blue };
    if (bmi < 25)   return { label: 'Normal weight', colour: COLOURS.green };
    if (bmi < 30)   return { label: 'Overweight',    colour: COLOURS.amber };
    return            { label: 'Obese',         colour: COLOURS.red };
  }
  function updateBMI() {
    var height = parseFloat(heightEl && heightEl.value);
    var weight = parseFloat(weightEl && weightEl.value);
    if (!height || !weight || height <= 0) {
      bmiValue.textContent = '—';
      bmiCat.textContent = 'enter height and weight';
      bmiCat.style.color = COLOURS.grey;
      bmiValue.style.color = COLOURS.grey;
      bmiBox.style.borderLeftColor = COLOURS.grey;
      return;
    }
    var metres = height / 100;
    var bmi = weight / (metres * metres);
    var info = bmiInfo(bmi);
    bmiValue.textContent = (Math.round(bmi * 10) / 10).toFixed(1);
    bmiValue.style.color = info.colour;
    bmiCat.textContent = info.label;
    bmiCat.style.color = info.colour;
    bmiBox.style.borderLeftColor = info.colour;
  }
  function checkBloodPressure() {
    var hi = parseFloat(apHiEl && apHiEl.value);
    var lo = parseFloat(apLoEl && apLoEl.value);
    if (isNaN(hi) || isNaN(lo)) {
      bpWarning.style.display = 'none';
      return true;
    }
    var message = null;
    if (hi <= lo) {
      message = 'Systolic blood pressure (' + hi + ') must be higher than ' +
                'diastolic (' + lo + '). The two readings may be swapped.';
    } else {
      var gap = hi - lo;
      if (gap < 20) {
        message = 'Pulse pressure is only ' + gap +
                  ' mmHg - please check the two readings.';
      } else if (gap > 100) {
        message = 'Pulse pressure is ' + gap +
                  ' mmHg - please check the two readings.';
      }
    }
    if (message) {
      bpWarning.textContent = message;
      bpWarning.style.display = 'block';
      apHiEl.classList.add('invalid');
      apLoEl.classList.add('invalid');
      return false;
    }
    bpWarning.style.display = 'none';
    apHiEl.classList.remove('invalid');
    apLoEl.classList.remove('invalid');
    return true;
  }
  function checkBMIPlausible() {
    var height = parseFloat(heightEl && heightEl.value);
    var weight = parseFloat(weightEl && weightEl.value);
    if (!height || !weight) return true;
    var bmi = weight / Math.pow(height / 100, 2);
    if (bmi < 12 || bmi > 60) {
      bpWarning.textContent = 'This height and weight give a BMI of ' +
        bmi.toFixed(1) + ', which is not plausible - please double-check them.';
      bpWarning.style.display = 'block';
      return false;
    }
    return true;
  }
  function revalidate() {
    updateBMI();
    checkBloodPressure();
  }
  [heightEl, weightEl].forEach(function (el) {
    if (el) el.addEventListener('input', function () {
      updateBMI();
      checkBMIPlausible();
    });
  });
  [apHiEl, apLoEl].forEach(function (el) {
    if (el) el.addEventListener('input', checkBloodPressure);
  });
  form.addEventListener('submit', function (e) {
    var ok = checkBloodPressure() && checkBMIPlausible();
    if (!ok) {
      e.preventDefault();
      return false;
    }
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = 'Analysing…';
    }
  });
  revalidate();
});
