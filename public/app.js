/* Poor Richard's Engineering Almanack — frontend */

(function () {
  'use strict';

  // DOM refs
  const dailySaying   = document.getElementById('daily-saying');
  const form          = document.getElementById('ask-form');
  const questionInput = document.getElementById('question');
  const askBtn        = document.getElementById('ask-btn');
  const answerSection = document.getElementById('answer-section');
  const answerText    = document.getElementById('answer-text');
  const proverbsList  = document.getElementById('proverbs-list');

  // ---- Saying of the day ----------------------------------------

  async function loadRandom() {
    try {
      const r = await fetch('/random');
      if (!r.ok) throw new Error(r.statusText);
      const data = await r.json();
      dailySaying.textContent = '\u201c' + data.text + '\u201d';
    } catch (e) {
      dailySaying.textContent = '\u201cExperience keeps a dear school, but fools will learn in no other.\u201d';
    }
  }

  loadRandom();

  // ---- Ask form --------------------------------------------------

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const question = questionInput.value.trim();
    if (!question) return;

    setLoading(true);
    clearAnswer();

    try {
      const r = await fetch('/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }),
      });

      if (r.status === 429) {
        showError('Poor Richard\u2019s daily counsel hath been exhausted, or thou hast asked too swiftly. Prithee wait a moment.');
        return;
      }
      if (!r.ok) {
        const body = await r.json().catch(() => ({}));
        showError(body.detail || 'An error occurred. Prithee try again.');
        return;
      }

      const data = await r.json();
      renderAnswer(data);
    } catch (err) {
      showError('Poor Richard\u2019s messenger hath gone astray. Check thy connection and try again.');
    } finally {
      setLoading(false);
    }
  });

  // ---- Render ----------------------------------------------------

  function renderAnswer(data) {
    answerText.textContent = data.answer;

    proverbsList.innerHTML = '';
    if (data.sayings && data.sayings.length) {
      data.sayings.forEach((s) => {
        const li = document.createElement('li');

        const textSpan = document.createElement('span');
        textSpan.className = 'saying-text';
        textSpan.textContent = '\u201c' + s.text + '\u201d';

        const metaSpan = document.createElement('span');
        metaSpan.className = 'saying-meta';
        const parts = [];
        if (s.year) parts.push(String(s.year));
        parts.push(Math.round(s.similarity * 100) + '% match');
        metaSpan.textContent = parts.join(' \u00b7 ');

        li.appendChild(textSpan);
        li.appendChild(metaSpan);
        proverbsList.appendChild(li);
      });
    } else {
      const li = document.createElement('li');
      li.textContent = 'No sufficiently relevant proverbs were retrieved for this question.';
      proverbsList.appendChild(li);
    }

    answerSection.hidden = false;
    answerSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  // ---- Helpers ---------------------------------------------------

  function setLoading(on) {
    askBtn.disabled = on;
    askBtn.textContent = on ? 'Consulting\u2026' : 'Seek Counsel';
  }

  function clearAnswer() {
    answerText.textContent = '';
    proverbsList.innerHTML = '';
    answerSection.hidden = true;
    // Remove any previous error
    const prev = form.querySelector('.error-msg');
    if (prev) prev.remove();
  }

  function showError(msg) {
    const p = document.createElement('p');
    p.className = 'error-msg';
    p.textContent = msg;
    form.appendChild(p);
    answerSection.hidden = true;
  }
})();
