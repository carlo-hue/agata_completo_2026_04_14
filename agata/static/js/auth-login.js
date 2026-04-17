/**
 * Auth Login Page - Form validation e UX enhancements
 *
 * Funzionalità:
 * - Validazione email in tempo reale
 * - Feedback visuale su submit
 * - Analytics tracking per login attempts
 * - Gestione errori (email non valida, etc.)
 */

document.addEventListener('DOMContentLoaded', function() {
    console.log('[AuthLogin] Module initialized');

    // Find email form
    const emailForm = document.querySelector('.email-form');
    const emailInput = document.querySelector('#email');
    const emailButton = document.querySelector('.email-button');

    if (!emailForm || !emailInput || !emailButton) {
        console.warn('[AuthLogin] Email form elements not found');
        return;
    }

    /**
     * Validazione email in tempo reale
     */
    emailInput.addEventListener('input', function() {
        const email = this.value.trim();
        const isValid = _isValidEmail(email);

        // Aggiorna stato bottone
        emailButton.disabled = !isValid;
        emailButton.style.opacity = isValid ? '1' : '0.5';
        emailButton.style.cursor = isValid ? 'pointer' : 'not-allowed';
    });

    /**
     * Submit form con feedback visuale
     */
    emailForm.addEventListener('submit', function(e) {
        e.preventDefault();

        const email = emailInput.value.trim();

        // Validazione finale
        if (!_isValidEmail(email)) {
            console.warn('[AuthLogin] Invalid email on submit:', email);
            _showError(emailInput, 'Email non valida');
            return;
        }

        // Disabilita bottone durante invio
        _disableButton(emailButton, 'Invio in corso...');

        // Traccia tentativo login
        _trackLoginAttempt('email_magic_link', email);

        // Invia form dopo short delay
        setTimeout(() => {
            emailForm.submit();
        }, 300);
    });

    /**
     * Validazione email semplice ma efficace
     * @param {string} email
     * @returns {boolean}
     */
    function _isValidEmail(email) {
        // Regex semplice ma sufficiente per UX
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email);
    }

    /**
     * Mostra errore sotto campo
     * @param {HTMLElement} element
     * @param {string} message
     */
    function _showError(element, message) {
        // Rimuovi errore precedente se esiste
        const existingError = element.parentElement.querySelector('.error-message');
        if (existingError) {
            existingError.remove();
        }

        // Aggiungi classe error al campo
        element.style.borderColor = '#ef4444';
        element.style.boxShadow = '0 0 0 3px rgba(239, 68, 68, 0.1)';

        // Crea elemento errore
        const errorEl = document.createElement('div');
        errorEl.className = 'error-message';
        errorEl.style.cssText = `
            font-size: 12px;
            color: #ef4444;
            margin-top: 6px;
            font-weight: 500;
        `;
        errorEl.textContent = message;
        element.parentElement.appendChild(errorEl);

        // Rimuovi errore dopo 4 secondi
        setTimeout(() => {
            element.style.borderColor = '#e2e8f0';
            element.style.boxShadow = '';
            if (errorEl.parentElement) {
                errorEl.remove();
            }
        }, 4000);
    }

    /**
     * Disabilita bottone durante submit
     * @param {HTMLElement} button
     * @param {string} loadingText
     */
    function _disableButton(button, loadingText) {
        const originalText = button.textContent;
        button.textContent = loadingText;
        button.disabled = true;
        button.style.opacity = '0.6';

        // Ripristina dopo timeout (fallback)
        setTimeout(() => {
            button.textContent = originalText;
            button.disabled = false;
            button.style.opacity = '1';
        }, 5000);
    }

    /**
     * Traccia tentativo login (per analytics)
     * @param {string} method - 'email_magic_link' | 'google_oauth'
     * @param {string} email - (opzionale)
     */
    function _trackLoginAttempt(method, email = null) {
        // Se disponibile, traccia con analytics service
        if (window.gtag) {
            window.gtag('event', 'login_attempt', {
                method: method,
                email_domain: email ? email.split('@')[1] : null,
            });
        }

        // Log locale
        console.log('[AuthLogin] Tracked login attempt:', {
            method: method,
            email_domain: email ? email.split('@')[1] : null,
            timestamp: new Date().toISOString(),
        });
    }

    /**
     * Traccia click su bottone Google
     */
    const googleButton = document.querySelector('.auth-button.google');
    if (googleButton) {
        googleButton.addEventListener('click', function() {
            _trackLoginAttempt('google_oauth');
        });
    }

    console.log('[AuthLogin] Form validation initialized');
});
