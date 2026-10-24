/**
 * Django Admin (Jazzmin) Custom Sidebar Navigation & Accordion
 * 
 * Features:
 * 1. Collapsible app menus with true accordion behavior (opening an app closes others).
 * 2. Automatic expansion and highlighting of active app and model on page load.
 * 3. Support for app index views (/admin/<app>/) as well as model changelist and changeform views.
 * 4. Smooth animated slide toggling and FontAwesome arrow rotation.
 */
(function ($) {
    'use strict';

    if (!$) {
        return;
    }

    /**
     * Automatically open the parent app menu for the current URL
     */
    function autoExpandActiveApp() {
        const path = window.location.pathname;

        // If dashboard/index, don't auto-open any app
        if (path === '/admin/' || path === '/admin') {
            return;
        }

        // Check if an item is already marked active by Jazzmin
        const $activeLink = $('a.nav-link.active');
        if ($activeLink.length) {
            const $parentLi = $activeLink.closest('li.nav-item.has-treeview');
            if ($parentLi.length) {
                $parentLi.addClass('menu-is-opening menu-open');
                $parentLi.children('ul.nav-treeview').show();
                return;
            }
        }

        // Match by exact URL
        const $directLink = $('#jazzy-navigation ul.nav-treeview a.nav-link[href="' + path + '"]');
        if ($directLink.length) {
            $directLink.addClass('active');
            const $parentLi = $directLink.closest('li.nav-item.has-treeview');
            $parentLi.addClass('menu-is-opening menu-open');
            $parentLi.children('ul.nav-treeview').show();
            return;
        }

        // Match by prefix (e.g. /admin/<app_label>/<model_name>/... or /admin/<app_label>/)
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

            // Fallback: match any link in the app
            if (!$matchedTreeview || !$matchedTreeview.length) {
                const appPrefix = '/admin/' + appLabel + '/';
                const $appLink = $('#jazzy-navigation ul.nav-treeview a.nav-link[href*="' + appPrefix + '"]');
                if ($appLink.length) {
                    $matchedTreeview = $appLink.first().closest('li.nav-item.has-treeview');
                }
            }

            if ($matchedTreeview && $matchedTreeview.length) {
                $matchedTreeview.addClass('menu-is-opening menu-open');
                $matchedTreeview.children('ul.nav-treeview').show();
            }
        }
    }

    /**
     * Initialize accordion click handler on app headers
     */
    function initAccordion() {
        const $nav = $('#jazzy-navigation');
        if (!$nav.length) {
            return;
        }

        // Ensure accordion attribute is set
        $nav.attr('data-accordion', 'true');

        // Intercept click on top-level app toggle links
        $nav.off('click.customAccordion').on('click.customAccordion', 'li.nav-item.has-treeview > a.nav-link', function (e) {
            e.preventDefault();
            e.stopPropagation();

            const $clickedLi = $(this).closest('li.nav-item.has-treeview');
            const $submenu = $clickedLi.children('ul.nav-treeview');
            const isCurrentlyOpen = $clickedLi.hasClass('menu-open');

            // Close all other open app menus (Accordion)
            $('li.nav-item.has-treeview.menu-open').not($clickedLi).each(function () {
                const $other = $(this);
                $other.removeClass('menu-open menu-is-opening');
                $other.children('ul.nav-treeview').stop(true, true).slideUp(200);
            });

            // Toggle clicked menu
            if (isCurrentlyOpen) {
                $clickedLi.removeClass('menu-open menu-is-opening');
                $submenu.stop(true, true).slideUp(200);
            } else {
                $clickedLi.addClass('menu-is-opening menu-open');
                $submenu.stop(true, true).slideDown(200);
            }
        });
    }

    $(document).ready(function () {
        initAccordion();
        autoExpandActiveApp();
    });

})(window.jQuery || window.$);
