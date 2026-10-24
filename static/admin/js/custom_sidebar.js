/**
 * Django Admin (Jazzmin) Custom Sidebar Navigation & Accordion
 * 
 * Features:
 * 1. Capture-phase click interception to completely eliminate collisions with AdminLTE bubble listeners.
 * 2. True Accordion behavior: clicking any app menu opens it and closes all other apps.
 * 3. Clicking an already open app smoothly collapses (closes) it.
 * 4. Automatic expansion and highlighting of active app and model on page load.
 * 5. Smooth animated slide toggling and FontAwesome arrow rotation.
 */
(function ($) {
    'use strict';

    /**
     * Automatically open the parent app menu for the current URL on page load
     */
    function autoExpandActiveApp() {
        const path = window.location.pathname;

        // If on dashboard/admin home, keep all apps collapsed
        if (path === '/admin/' || path === '/admin') {
            return;
        }

        // 1. Check if Jazzmin already highlighted an active link
        const $activeLink = $('#jazzy-navigation ul.nav-treeview a.nav-link.active');
        if ($activeLink.length) {
            const $parentLi = $activeLink.closest('li.nav-item.has-treeview');
            if ($parentLi.length) {
                $parentLi.addClass('menu-is-opening menu-open');
                $parentLi.children('ul.nav-treeview').css('display', 'block');
                return;
            }
        }

        // 2. Direct match by exact pathname
        const $directLink = $('#jazzy-navigation ul.nav-treeview a.nav-link[href="' + path + '"]');
        if ($directLink.length) {
            $directLink.addClass('active');
            const $parentLi = $directLink.closest('li.nav-item.has-treeview');
            $parentLi.addClass('menu-is-opening menu-open');
            $parentLi.children('ul.nav-treeview').css('display', 'block');
            return;
        }

        // 3. Match by URL prefix: /admin/<app_label>/<model_name>/... or /admin/<app_label>/
        const match = path.match(/^\/admin\/([a-zA-Z0-9_-]+)(?:\/([a-zA-Z0-9_-]+))?/);
        if (match) {
            const appLabel = match[1];
            const modelName = match[2];

            let $matchedTreeview = null;

            // Try matching model prefix first
            if (modelName) {
                const modelPrefix = '/admin/' + appLabel + '/' + modelName + '/';
                const $modelLink = $('#jazzy-navigation ul.nav-treeview a.nav-link[href^="' + modelPrefix + '"]');
                if ($modelLink.length) {
                    $modelLink.first().addClass('active');
                    $matchedTreeview = $modelLink.first().closest('li.nav-item.has-treeview');
                }
            }

            // Fallback: match any link belonging to this app
            if (!$matchedTreeview || !$matchedTreeview.length) {
                const appPrefix = '/admin/' + appLabel + '/';
                const $appLink = $('#jazzy-navigation ul.nav-treeview a.nav-link[href*="' + appPrefix + '"]');
                if ($appLink.length) {
                    $matchedTreeview = $appLink.first().closest('li.nav-item.has-treeview');
                }
            }

            if ($matchedTreeview && $matchedTreeview.length) {
                $matchedTreeview.addClass('menu-is-opening menu-open');
                $matchedTreeview.children('ul.nav-treeview').css('display', 'block');
            }
        }
    }

    /**
     * Intercept clicks on top-level app headers in the CAPTURE phase.
     * This stops AdminLTE's bubble listener from running and guarantees
     * 100% collision-free accordion and toggle behavior.
     */
    function initCaptureAccordion() {
        document.addEventListener('click', function (e) {
            // Find if click was on or inside a top-level app toggle link in #jazzy-navigation
            const appToggleLink = e.target.closest('#jazzy-navigation > li.nav-item.has-treeview > a.nav-link');
            if (!appToggleLink) {
                return;
            }

            // Stop event immediately so AdminLTE 4 bubble listener NEVER runs
            e.preventDefault();
            e.stopPropagation();
            e.stopImmediatePropagation();

            const parentLi = appToggleLink.closest('li.nav-item.has-treeview');
            if (!parentLi) {
                return;
            }

            const submenu = parentLi.querySelector('ul.nav-treeview');
            if (!submenu) {
                return;
            }

            const isCurrentlyOpen = parentLi.classList.contains('menu-open');

            // Accordion: close all other open app treeviews
            const openItems = document.querySelectorAll('#jazzy-navigation > li.nav-item.has-treeview.menu-open');
            openItems.forEach(function (item) {
                if (item !== parentLi) {
                    item.classList.remove('menu-open', 'menu-is-opening');
                    const sub = item.querySelector('ul.nav-treeview');
                    if (sub) {
                        $(sub).stop(true, true).slideUp(200, function () {
                            this.style.display = 'none';
                        });
                    }
                }
            });

            // Toggle clicked menu
            if (isCurrentlyOpen) {
                parentLi.classList.remove('menu-open', 'menu-is-opening');
                $(submenu).stop(true, true).slideUp(200, function () {
                    this.style.display = 'none';
                });
            } else {
                parentLi.classList.add('menu-is-opening', 'menu-open');
                $(submenu).stop(true, true).slideDown(200, function () {
                    this.style.display = 'block';
                });
            }
        }, true); // useCapture = true ensures this fires before any bubble listener
    }

    // Attach capture listener immediately
    initCaptureAccordion();

    // Auto-expand active app when DOM is ready
    $(document).ready(function () {
        autoExpandActiveApp();
    });

})(window.jQuery || window.$);
