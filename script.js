(function () {
  var cats = [
    ['all', 'All'], ['pregnancy', 'Pregnancy'], ['feeding', 'Feeding'], ['postnatal', 'Postnatal'],
    ['play', 'Baby and toddler'], ['partners', 'Partners'], ['workshops', 'Workshops']
  ];
  var sessions = [
    ['pregnancy', 'Pregnancy coffee mornings and due-date groups', 'Meet others expecting around the same time, with a midwife to ask the questions you’ve been saving up.', 'Sample: weekday mornings', 'Free'],
    ['pregnancy', 'Antenatal classes and birth preparation', 'Relaxed, practical preparation for birth and the first weeks, in small friendly groups.', 'Sample: evenings and weekends', 'Paid'],
    ['feeding', 'Breastfeeding and infant feeding support café', 'Drop in for hands-on, judgement-free advice on any way of feeding your baby.', 'Sample: weekly drop-in', 'Free'],
    ['postnatal', 'Newborn and postnatal meet-ups', 'Bring your baby, have a hot drink and find your people in those early weeks.', 'Sample: weekly', 'Free'],
    ['postnatal', 'Postnatal recovery and emotional wellbeing workshops', 'Gentle sessions on healing, rest and looking after yourself as well as your baby.', 'Sample: monthly', 'Paid'],
    ['postnatal', 'Birth debrief sessions and birth story groups', 'A safe space to talk through your birth with a midwife and others who understand.', 'Sample: monthly', 'Low-cost'],
    ['play', 'Baby sensory', 'Lights, textures and sounds to explore together.', 'Sample: weekday mornings', 'Paid'],
    ['play', 'Baby massage', 'Learn simple techniques to soothe and bond with your baby.', 'Sample: short course', 'Paid'],
    ['play', 'Toddler play sessions', 'Free play in the play corner while grown-ups chat nearby.', 'Sample: most days', 'Paid'],
    ['partners', 'Dad and partner groups', 'A relaxed group for dads and partners to share the ups, downs and nappy tips.', 'Sample: evenings or Saturdays', 'Free'],
    ['workshops', 'Baby first-aid workshops', 'Practical, confidence-building first aid for parents and carers.', 'Sample: monthly', 'Paid'],
    ['workshops', 'Guest speakers', 'Sleep, weaning, returning to work and more, from people who know their stuff.', 'Sample: occasional', 'Low-cost']
  ];
  var nameList = ['The Village', 'The Nest', 'Bump, Baby & Beyond', 'Milk & Mugs'];
  var interestList = ['Pregnancy groups', 'Antenatal classes', 'Feeding support', 'Newborn meet-ups', 'Baby sensory and massage', 'Toddler play', 'Dads and partners', 'Workshops', 'Café and coffee'];

  var filter = 'all', brand = nameList[0], picked = [];

  function el(tag, attrs, text) {
    var e = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) { e.setAttribute(k, attrs[k]); });
    if (text) e.textContent = text;
    return e;
  }
  function chip(label, pressed, onClick) {
    var b = el('button', { type: 'button', 'class': 'chip', 'aria-pressed': String(pressed) }, label);
    b.addEventListener('click', onClick);
    return b;
  }

  function renderFilters() {
    var box = document.getElementById('filters');
    box.textContent = '';
    cats.forEach(function (c) {
      box.appendChild(chip(c[1], filter === c[0], function () { filter = c[0]; renderFilters(); renderSessions(); }));
    });
  }
  function renderSessions() {
    var box = document.getElementById('sessions');
    box.textContent = '';
    var shown = sessions.filter(function (s) { return filter === 'all' || s[0] === filter; });
    shown.forEach(function (s) {
      var card = el('article', { 'class': 'card session' });
      var row = el('div', { 'class': 'row' });
      row.appendChild(el('span', { 'class': 'when' }, s[3]));
      row.appendChild(el('span', { 'class': 'tag ' + s[4] }, s[4]));
      card.appendChild(row);
      card.appendChild(el('h3', {}, s[1]));
      card.appendChild(el('p', {}, s[2]));
      box.appendChild(card);
    });
    document.getElementById('count').textContent = 'Showing ' + shown.length + (shown.length === 1 ? ' session' : ' sessions');
  }
  function renderNames() {
    var box = document.getElementById('names');
    box.textContent = '';
    nameList.forEach(function (n) {
      box.appendChild(chip(n, brand === n, function () {
        brand = n;
        document.querySelectorAll('.js-brand').forEach(function (x) { x.textContent = n; });
        renderNames();
      }));
    });
  }
  function renderInterests() {
    var box = document.getElementById('interests');
    box.textContent = '';
    interestList.forEach(function (label) {
      var on = picked.indexOf(label) !== -1;
      box.appendChild(chip(label, on, function () {
        picked = on ? picked.filter(function (x) { return x !== label; }) : picked.concat([label]);
        renderInterests();
      }));
    });
  }

  var form = document.getElementById('form');
  var thanks = document.getElementById('thanks');
  var error = document.getElementById('error');
  form.addEventListener('submit', function (e) {
    e.preventDefault();
    var name = document.getElementById('f-name').value.trim();
    var email = document.getElementById('f-email').value.trim();
    if (!name || !/\S+@\S+\.\S+/.test(email)) {
      error.textContent = 'Please add your name and a valid email address.';
      error.hidden = false;
      return;
    }
    error.hidden = true;
    document.getElementById('first').textContent = name.split(' ')[0];
    form.hidden = true;
    thanks.hidden = false;
  });
  document.getElementById('again').addEventListener('click', function () {
    form.reset();
    picked = [];
    renderInterests();
    thanks.hidden = true;
    form.hidden = false;
  });

  renderFilters(); renderSessions(); renderNames(); renderInterests();
})();
