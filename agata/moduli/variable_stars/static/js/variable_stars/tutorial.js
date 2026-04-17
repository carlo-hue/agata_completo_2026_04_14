/**
 * Tutorial - Guida interattiva step-by-step per l'analisi di stelle variabili
 *
 * Mostra un ribbon persistente in cima all'editor con navigazione Avanti/Indietro.
 * Ad ogni step: switcha il tab corretto e apre il pannello help con le istruzioni.
 * I testi degli step sono caricati via API help (/agata/help/api/article/editor.tutorial.*),
 * rendendo ogni step editabile dal superuser tramite il pannello offcanvas esistente.
 *
 * Help IDs: editor.tutorial.step1 ... editor.tutorial.step9
 *
 * Dependencies:
 *   - window.openHelpPanel (da macros.html)
 */

const TUTORIAL_STEPS = [
  { label: 'Trova il progetto',    tab: null,               helpId: 'editor.tutorial.step1' },
  { label: 'Carica i dati',        tab: null,               helpId: 'editor.tutorial.step2' },
  { label: 'Interroga i cataloghi', tab: 'tab-catalogs',     helpId: 'editor.tutorial.step3' },
  { label: 'Field Star Map',       tab: 'tab-field-star-map', helpId: 'editor.tutorial.step4' },
  { label: 'Importa dati esterni', tab: 'tab-import-catalogs', helpId: 'editor.tutorial.step5' },
  { label: 'Allinea le sessioni',  tab: 'tab-lc',           helpId: 'editor.tutorial.step6' },
  { label: 'Sigma clipping',       tab: 'tab-lc',           helpId: 'editor.tutorial.step7' },
  { label: 'Periodogramma',        tab: 'tab-period',       helpId: 'editor.tutorial.step8' },
  { label: 'Analisi in fase',      tab: 'tab-phase',        helpId: 'editor.tutorial.step9' },
];

let _currentStep = 0;
let _active = false;

/**
 * Inizializza il modulo tutorial. Collega i pulsanti del ribbon.
 */
export function initTutorial() {
  console.log('[Tutorial] Module initialized');

  const prevBtn = document.getElementById('tutorial-prev');
  const nextBtn = document.getElementById('tutorial-next');
  const closeBtn = document.getElementById('tutorial-close');
  const guideBtn = document.getElementById('tutorial-guide');

  if (prevBtn) prevBtn.addEventListener('click', _prevStep);
  if (nextBtn) nextBtn.addEventListener('click', _nextStep);
  if (closeBtn) closeBtn.addEventListener('click', _closeTutorial);
  if (guideBtn) guideBtn.addEventListener('click', () => {
    if (_active) window.openHelpPanel(TUTORIAL_STEPS[_currentStep].helpId);
  });
}

/**
 * Avvia il tutorial dal passo indicato (default: passo 3, indice 2).
 * @param {number} [fromStep=2] - Indice 0-based da cui partire
 */
export function startTutorial(fromStep = 2) {
  _currentStep = fromStep;
  console.log(`[Tutorial] Starting from step ${_currentStep + 1}`);
  _active = true;
  const ribbon = document.getElementById('tutorial-ribbon');
  if (ribbon) ribbon.style.display = 'flex';
  _applyStep(_currentStep);
}

window.startTutorial = startTutorial;

// ─── Privato ──────────────────────────────────────────────────────────────────

function _prevStep() {
  if (!_active || _currentStep <= 0) return;
  _currentStep--;
  _applyStep(_currentStep);
}

function _nextStep() {
  if (!_active) return;
  if (_currentStep >= TUTORIAL_STEPS.length - 1) {
    _closeTutorial();
    return;
  }
  _currentStep++;
  _applyStep(_currentStep);
}

function _closeTutorial() {
  _active = false;
  const ribbon = document.getElementById('tutorial-ribbon');
  if (ribbon) ribbon.style.display = 'none';
  const closeBtn = document.querySelector('#helpOffcanvas [data-help-close]');
  if (closeBtn) closeBtn.click();
  console.log('[Tutorial] Tutorial closed');
}

function _applyStep(idx) {
  const step = TUTORIAL_STEPS[idx];
  if (!step) return;

  console.log(`[Tutorial] Step ${idx + 1}/${TUTORIAL_STEPS.length}: ${step.label}`);
  _updateRibbonUI(idx);

  if (step.tab) {
    const tabBtn = document.querySelector(`.tab-btn[onclick*="${step.tab}"]`);
    if (tabBtn) tabBtn.click();
  }

  if (typeof window.openHelpPanel === 'function') {
    window.openHelpPanel(step.helpId);
  }
}

function _updateRibbonUI(idx) {
  const step = TUTORIAL_STEPS[idx];
  const counter = document.getElementById('tutorial-counter');
  const label = document.getElementById('tutorial-step-label');
  const prevBtn = document.getElementById('tutorial-prev');
  const nextBtn = document.getElementById('tutorial-next');
  const progress = document.getElementById('tutorial-progress-fill');

  if (counter) counter.textContent = `${idx + 1}/${TUTORIAL_STEPS.length}`;
  if (label) label.textContent = step.label;
  if (prevBtn) prevBtn.disabled = idx === 0;
  if (nextBtn) nextBtn.textContent = idx === TUTORIAL_STEPS.length - 1 ? 'Fine ✓' : 'Avanti →';
  if (progress) progress.style.width = `${Math.round(((idx + 1) / TUTORIAL_STEPS.length) * 100)}%`;
}
