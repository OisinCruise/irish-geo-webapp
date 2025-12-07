/**
 * Irish Historical Sites GIS - Internationalization (i18n)
 * =========================================================
 * Handles English/Irish (Gaeilge) language switching
 */

(function() {
    'use strict';

    const LANG_KEY = 'irish-gis-lang';
    const LANG_EN = 'en';
    const LANG_GA = 'ga';

    /**
     * Get the current language from localStorage or default to English
     */
    function getCurrentLang() {
        return localStorage.getItem(LANG_KEY) || LANG_EN;
    }

    /**
     * Apply language to the document
     */
    function applyLanguage(lang) {
        document.documentElement.setAttribute('data-lang', lang);
        document.documentElement.setAttribute('lang', lang);
        localStorage.setItem(LANG_KEY, lang);

        // Update all translatable elements
        updateTranslatableElements(lang);
        updateLangIndicator(lang);
    }

    /**
     * Update all elements with data-en and data-ga attributes
     */
    function updateTranslatableElements(lang) {
        const elements = document.querySelectorAll('[data-en][data-ga]');
        elements.forEach(el => {
            const text = el.getAttribute(`data-${lang}`);
            if (text) {
                el.textContent = text;
            }
        });

        // Update placeholders
        const inputElements = document.querySelectorAll('[data-placeholder-en][data-placeholder-ga]');
        inputElements.forEach(el => {
            const placeholder = el.getAttribute(`data-placeholder-${lang}`);
            if (placeholder) {
                el.setAttribute('placeholder', placeholder);
            }
        });
    }

    /**
     * Update the language toggle button indicator
     */
    function updateLangIndicator(lang) {
        const langToggle = document.getElementById('langToggle');
        if (langToggle) {
            const indicator = langToggle.querySelector('.lang-indicator');
            if (indicator) {
                // Show the OTHER language (the one you'll switch to)
                indicator.textContent = lang === LANG_EN ? 'GA' : 'EN';
            }
        }
    }

    /**
     * Toggle between English and Irish
     */
    function toggleLanguage() {
        const currentLang = document.documentElement.getAttribute('data-lang') || LANG_EN;
        const newLang = currentLang === LANG_EN ? LANG_GA : LANG_EN;
        applyLanguage(newLang);

        // Dispatch custom event for map and other components to react
        document.dispatchEvent(new CustomEvent('languageChanged', {
            detail: { language: newLang }
        }));
    }

    /**
     * Get translation for a key based on current language
     */
    function t(enText, gaText) {
        const lang = getCurrentLang();
        return lang === LANG_GA ? gaText : enText;
    }

    /**
     * Initialize language on page load
     */
    function initLanguage() {
        const lang = getCurrentLang();
        applyLanguage(lang);

        // Set up toggle button listener
        const langToggle = document.getElementById('langToggle');
        if (langToggle) {
            langToggle.addEventListener('click', toggleLanguage);
        }
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initLanguage);
    } else {
        initLanguage();
    }

    // Expose functions globally
    window.IrishGIS = window.IrishGIS || {};
    window.IrishGIS.toggleLanguage = toggleLanguage;
    window.IrishGIS.getCurrentLang = getCurrentLang;
    window.IrishGIS.t = t;
    window.IrishGIS.LANG_EN = LANG_EN;
    window.IrishGIS.LANG_GA = LANG_GA;

})();
