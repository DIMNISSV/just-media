// catalog/static/catalog/js/media_detail_handler.js
document.addEventListener('DOMContentLoaded', () => {
    // --- DOM Elements ---
    const playerPlaceholder = document.getElementById('player-placeholder');
    const episodesContainer = document.getElementById('seasons-tab-content');
    const nextEpisodeBtn = document.getElementById('next-episode-btn');
    const prevEpisodeBtn = document.getElementById('prev-episode-btn');
    const playerUrlTemplateEl = document.getElementById('player-url-template');
    // Translation elements
    const translationSelectorPlaceholder = document.getElementById('translation-selector-placeholder'); // Main container
    const translationLabel = translationSelectorPlaceholder?.querySelector('.translation-label'); // Static label
    const translationButtonsContainer = document.getElementById('translation-buttons-container'); // Buttons go here
    const noTranslationsMessage = document.getElementById('no-translations-message'); // Message span
    // ---
    const episodesLinksDataElement = document.getElementById('episodes-links-data');
    const mainLinksDataElement = document.getElementById('main-links-data');
    const mediaPk = document.getElementById('seasons-tab-content')?.dataset.mediaPk;
    const watchAreaRow = document.getElementById('watch-area-row'); // Bootstrap row
    const playerContainerColumn = document.getElementById('player-container-column'); // Player's column
    const episodeListColumn = document.getElementById('episodes-container-column'); // Episodes' column
    const layoutRadios = document.querySelectorAll('input[name="playerLayout"]');
    const playerOnlyRadio = document.getElementById('layoutPlayerOnly');
    const playerOnlyLabel = document.querySelector('label[for="layoutPlayerOnly"]');

    // --- State Variables ---
    let currentEpisodeElement = null;
    let currentSelectedTranslationId = null;
    let episodesLinksData = {};
    let mainLinksData = {};
    let currentLayout = 'episodes_below';

    // --- Constants ---
    const LAST_EPISODE_KEY = mediaPk ? `last_watched_episode_${mediaPk}` : null;
    const LAST_TRANSLATION_KEY = mediaPk ? `last_selected_translation_${mediaPk}` : null;
    const LAST_DETAIL_TAB_KEY = mediaPk ? `last_detail_tab_${mediaPk}` : null;
    const PLAYER_LAYOUT_KEY = `player_layout_preference`;
    const PLAYER_URL_TEMPLATE = playerUrlTemplateEl?.dataset.url;
    const LAYOUTS = ['episodes_below', 'episodes_right', 'player_only'];
    const SCROLL_CLASS = 'episodes-sidebar-scroll'; // Applied to episodeListColumn
    const LIST_VIEW_CLASS = 'episodes-list-view'; // Added to episodeListColumn for list styling

    // --- Utility Functions ---
    function parseJsonData(element, description) {
        if (!element) {
            console.warn(`${description} data element not found.`);
            return {};
        }
        try {
            return JSON.parse(element.textContent || '{}');
        } catch (e) {
            console.error(`Error parsing ${description} data:`, e);
            return {};
        }
    }

    function generatePlayerUrl(linkPk) {
        if (!PLAYER_URL_TEMPLATE || !linkPk) return null;
        // Ensure we replace only the number part, keeping the base URL structure
        return PLAYER_URL_TEMPLATE.replace(/(\/play\/)\d+(\/)/, `$1${linkPk}$2`);
    }

    function getStartFromValue(linkData) {
        // Safely access start_from, defaulting to null
        return linkData?.start_from ?? null;
    }

    // --- Core Logic Functions ---
    function loadPlayer(linkPk, translationIdToSave, startFrom = null) {
        const playerUrl = generatePlayerUrl(linkPk);
        console.log(`Attempting to load player for link PK: ${linkPk}, Translation ID: ${translationIdToSave}, URL: ${playerUrl}, StartFrom: ${startFrom}`);
        if (playerUrl && playerPlaceholder) {
            // Use the potentially modified URL from the play_source_link view context
            playerPlaceholder.innerHTML = `<div class="player-container"><iframe src="${playerUrl}" allowfullscreen="allowfullscreen" webkitallowfullscreen="webkitallowfullscreen" mozallowfullscreen="mozallowfullscreen" loading="eager"></iframe></div>`;

            // Save state to localStorage
            if (LAST_TRANSLATION_KEY && translationIdToSave) {
                localStorage.setItem(LAST_TRANSLATION_KEY, translationIdToSave);
                currentSelectedTranslationId = translationIdToSave.toString(); // Ensure string for comparison
                console.log(`Saved last translation ID: ${currentSelectedTranslationId}`);
            }
            // Save episode only if not in player_only mode OR if we are transitioning away from it
            if (currentEpisodeElement && LAST_EPISODE_KEY && currentLayout !== 'player_only') {
                const episodePk = currentEpisodeElement.dataset.episodePk;
                localStorage.setItem(LAST_EPISODE_KEY, episodePk);
                console.log(`Saved last episode PK: ${episodePk}`);
            } else if (!currentEpisodeElement && LAST_EPISODE_KEY && currentLayout === 'player_only') {
                // Don't clear the last episode PK when entering player_only mode
                console.log("In player_only mode, keeping last episode PK if previously set.");
            }

            // Optional: Send message to loaded iframe if needed
            const iframe = playerPlaceholder.querySelector('iframe');
            if (iframe) {
                iframe.onload = () => {
                    try {
                        const message = {type: 'playerInfo', startFrom: startFrom};
                        iframe.contentWindow.postMessage(message, '*');
                    } catch (e) {
                        console.warn("Could not post message to iframe.", e);
                    }
                };
            }

        } else {
            console.error('Could not generate player URL or player placeholder not found.');
            playerPlaceholder.innerHTML = '<p class="text-danger text-center p-5">{% trans "Error loading player." %}</p>';
        }
    }

    function displayTranslationOptions(episodePk, preferredTranslationId = null) {
        // Ensure the target containers exist
        if (!translationButtonsContainer || !translationLabel || !noTranslationsMessage) {
            console.error("Translation UI elements not found!");
            return null;
        }

        let links = [];
        let isMainLinkContext = (currentLayout === 'player_only');

        if (isMainLinkContext) {
            // Use Object.values to get an array of link objects
            links = Object.values(mainLinksData);
            links.sort((a, b) => a.translation_title.localeCompare(b.translation_title)); // Sort by title
            console.log(`Displaying translations for MAIN ITEM using ${links.length} main links.`);
        } else if (episodePk && episodesLinksData[episodePk]) {
            links = episodesLinksData[episodePk]; // Already an array
            console.log(`Displaying translations for EPISODE ${episodePk} using ${links.length} episode links.`);
        } else {
            console.log(`No links found for context. Layout: ${currentLayout}, Episode PK: ${episodePk}`);
        }

        // Clear previous buttons and hide messages/label initially
        translationButtonsContainer.innerHTML = '';
        translationLabel.style.display = 'none';
        noTranslationsMessage.style.display = 'none';

        let translationLinkToAutoLoad = null;

        if (links.length > 0) {
            translationLabel.style.display = ''; // Show the static label

            let preferredLink = null;
            // Ensure preferredTranslationId is treated as a string for comparison
            const preferredIdStr = preferredTranslationId?.toString();
            if (preferredIdStr) {
                // Compare string IDs
                preferredLink = links.find(link => link.translation_id?.toString() === preferredIdStr);
                console.log(`Preferred translation ID ${preferredIdStr} found in links: ${!!preferredLink}`);
            }

            // Fallback to the first link if no preference matches
            translationLinkToAutoLoad = preferredLink || links[0];
            console.log(`Auto-loading translation: ${translationLinkToAutoLoad?.translation_title} (PK: ${translationLinkToAutoLoad?.link_pk})`);

            // Generate buttons HTML and append to the container
            let buttonsHtml = '';
            links.forEach(link => {
                const quality = link.quality ? ` (${link.quality})` : '';
                const isSelected = translationLinkToAutoLoad && link.link_pk === translationLinkToAutoLoad.link_pk;
                const btnClass = isSelected ? 'btn-primary active' : 'btn-outline-primary';
                const startFromAttr = link.start_from ? `data-start-from="${link.start_from}"` : '';
                buttonsHtml += `<button class="btn btn-sm ${btnClass} me-1 mb-1 translation-btn"
                                       data-link-pk="${link.link_pk}"
                                       data-translation-id="${link.translation_id}"
                                       ${startFromAttr}>
                                    ${link.translation_title}${quality}
                                </button>`;
            });
            translationButtonsContainer.innerHTML = buttonsHtml; // Set buttons HTML

            return translationLinkToAutoLoad; // Return the link object to be loaded

        } else {
            noTranslationsMessage.style.display = ''; // Show the 'no translations' message
            // Clear the player if no translations are found
            if (playerPlaceholder) {
                playerPlaceholder.innerHTML = '<div class="text-center text-muted border rounded p-5">{% trans "No content available." %}</div>';
            }
            return null; // Indicate no link to load
        }
    }

    function highlightEpisode(episodeElement) {
        // Remove highlight from all episode selectors first
        document.querySelectorAll('#seasons-tab-content .episode-selector.active').forEach(el => {
            el.classList.remove('active', 'border', 'border-primary', 'border-3'); // Ensure all related classes are removed
        });

        if (episodeElement) {
            // Add highlight to the selected element
            episodeElement.classList.add('active', 'border', 'border-primary', 'border-3');
            currentEpisodeElement = episodeElement; // Update current element state

            // Scroll into view if in sidebar mode
            if (episodeListColumn?.classList.contains(SCROLL_CLASS)) {
                episodeElement.scrollIntoView({behavior: 'smooth', block: 'nearest'});
            }
        } else {
            currentEpisodeElement = null; // Clear current element state if null passed
        }
        updateNavButtons(); // Update prev/next buttons state
    }


    function highlightTranslationButton(buttonElement) {
        // Target buttons within the specific container now
        translationButtonsContainer?.querySelectorAll('.translation-btn.active').forEach(btn => {
            btn.classList.remove('active', 'btn-primary');
            btn.classList.add('btn-outline-primary');
        });
        if (buttonElement) {
            buttonElement.classList.remove('btn-outline-primary');
            buttonElement.classList.add('active', 'btn-primary');
        }
    }

    function findEpisodeElementByPk(episodePk) {
        if (!episodesContainer || !episodePk) return null;
        // Ensure we select within the correct container
        return episodesContainer.querySelector(`.episode-selector[data-episode-pk='${episodePk}']`);
    }

    function findNextEpisodeElement(currentElement) {
        if (!currentElement) return null;

        const currentEpisodePk = currentElement.dataset.episodePk; // For logging
        const parentCol = currentElement.closest('.col');
        if (!parentCol) {
            console.warn(`[findNext] Could not find parent .col for episode PK ${currentEpisodePk}`);
            return null; // Should not happen with current HTML structure
        }

        let nextElement = null;
        let nextCol = parentCol.nextElementSibling;

        // Find the next sibling .col that contains an .episode-selector
        while (nextCol && !nextCol.querySelector('.episode-selector')) {
            nextCol = nextCol.nextElementSibling;
        }

        if (nextCol) {
            nextElement = nextCol.querySelector('.episode-selector');
            console.log(`[findNext] Found next element PK ${nextElement?.dataset.episodePk} in next column.`);
        } else {
            console.log(`[findNext] No next sibling column found for episode PK ${currentEpisodePk}. Checking next season.`);
            // If no next column found within the current season tab pane, check next tab
            const currentTabPane = currentElement.closest('.tab-pane');
            if (!currentTabPane) return null;
            const nextTabPane = currentTabPane.nextElementSibling;

            if (nextTabPane?.classList.contains('tab-pane')) {
                // Activate the next season tab
                const nextTabButton = document.getElementById(nextTabPane.getAttribute('aria-labelledby'));
                if (nextTabButton) {
                    try {
                        new bootstrap.Tab(nextTabButton).show();
                    } catch (e) {
                        console.error("Bootstrap tab error:", e)
                    }
                }
                // Find the first episode selector in the new tab pane
                nextElement = nextTabPane.querySelector('.episode-selector');
                console.log(`[findNext] Switched to next season tab. First episode: ${nextElement?.dataset.episodePk}`);
            } else {
                console.log("[findNext] No next season tab found.");
            }
        }
        return nextElement;
    }

    function findPrevEpisodeElement(currentElement) {
        if (!currentElement) return null;

        const currentEpisodePk = currentElement.dataset.episodePk; // For logging
        const parentCol = currentElement.closest('.col');
        if (!parentCol) {
            console.warn(`[findPrev] Could not find parent .col for episode PK ${currentEpisodePk}`);
            return null;
        }

        let prevElement = null;
        let prevCol = parentCol.previousElementSibling;

        // Find the previous sibling .col that contains an .episode-selector
        while (prevCol && !prevCol.querySelector('.episode-selector')) {
            prevCol = prevCol.previousElementSibling;
        }

        if (prevCol) {
            prevElement = prevCol.querySelector('.episode-selector');
            console.log(`[findPrev] Found previous element PK ${prevElement?.dataset.episodePk} in previous column.`);
        } else {
            console.log(`[findPrev] No previous sibling column found for episode PK ${currentEpisodePk}. Checking previous season.`);
            // If no previous column found within the current season tab pane, check previous tab
            const currentTabPane = currentElement.closest('.tab-pane');
            if (!currentTabPane) return null;
            const prevTabPane = currentTabPane.previousElementSibling;

            if (prevTabPane?.classList.contains('tab-pane')) {
                // Activate the previous season tab
                const prevTabButton = document.getElementById(prevTabPane.getAttribute('aria-labelledby'));
                if (prevTabButton) {
                    try {
                        new bootstrap.Tab(prevTabButton).show();
                    } catch (e) {
                        console.error("Bootstrap tab error:", e)
                    }
                }
                // Find the last episode selector in the new tab pane
                const episodes = prevTabPane.querySelectorAll('.episode-selector');
                prevElement = episodes.length > 0 ? episodes[episodes.length - 1] : null;
                console.log(`[findPrev] Switched to previous season tab. Last episode: ${prevElement?.dataset.episodePk}`);
            } else {
                console.log("[findPrev] No previous season tab found.");
            }
        }
        return prevElement;
    }


    function updateNavButtons() {
        const nextElement = findNextEpisodeElement(currentEpisodeElement);
        const prevElement = findPrevEpisodeElement(currentEpisodeElement);

        // Show/hide the entire nav container based on player_only mode
        const navContainer = episodeListColumn?.querySelector('.d-flex.justify-content-between.align-items-center');
        if (navContainer) {
            navContainer.style.display = (currentLayout === 'player_only') ? 'none' : '';
        }

        // Enable/disable buttons based on element existence and layout mode
        if (nextEpisodeBtn) nextEpisodeBtn.disabled = !nextElement || currentLayout === 'player_only';
        if (prevEpisodeBtn) prevEpisodeBtn.disabled = !prevElement || currentLayout === 'player_only';
    }


    function handleEpisodeSelection(episodeElement, manuallyClicked = false) {
        // Ignore if in player_only mode or element is invalid
        if (!episodeElement || currentLayout === 'player_only') {
            console.log("Episode selection ignored. Element:", episodeElement, "Layout:", currentLayout);
            return;
        }

        const episodePk = episodeElement.dataset.episodePk;
        console.log(`Handling episode selection for PK: ${episodePk}, Manual Click: ${manuallyClicked}`);

        highlightEpisode(episodeElement); // Highlight the selected episode visually

        // Determine the translation to use: last stored, or current if nothing stored
        const preferredTranslationId = LAST_TRANSLATION_KEY ? localStorage.getItem(LAST_TRANSLATION_KEY) : currentSelectedTranslationId;
        console.log(`Preferred Translation ID for episode selection: ${preferredTranslationId}`);

        // Update translation buttons and get the link to load
        const translationLinkToLoad = displayTranslationOptions(episodePk, preferredTranslationId);

        if (translationLinkToLoad) {
            const startFrom = getStartFromValue(translationLinkToLoad);
            loadPlayer(translationLinkToLoad.link_pk, translationLinkToLoad.translation_id.toString(), startFrom);

            // Highlight the corresponding translation button
            const translationButton = translationButtonsContainer?.querySelector(`.translation-btn[data-link-pk='${translationLinkToLoad.link_pk}']`);
            highlightTranslationButton(translationButton);
        } else {
            // If no translation link is found (e.g., episode has no sources)
            console.log(`No translation link to load for episode PK ${episodePk}`);
            if (playerPlaceholder) {
                playerPlaceholder.innerHTML = '<div class="text-center text-muted border rounded p-5">{% trans "No translations found for this episode." %}</div>';
            }
            currentSelectedTranslationId = null; // Clear current selection state
            highlightTranslationButton(null); // Clear button highlight
        }

        // Switch to 'Watch' tab if the selection was manually triggered by the user
        const watchTabButton = document.getElementById('watch-tab');
        if (manuallyClicked && watchTabButton && !watchTabButton.classList.contains('active')) {
            try {
                new bootstrap.Tab(watchTabButton).show();
            } catch (e) {
                console.error("Bootstrap tab error:", e)
            }
        }
    }


    function restoreLastWatchedState() {
        // Handle player_only mode first
        if (currentLayout === 'player_only') {
            console.log("Restore Watched State: In player_only layout.");
            const preferredTranslationId = LAST_TRANSLATION_KEY ? localStorage.getItem(LAST_TRANSLATION_KEY) : null;
            // Display main links and get the one to load
            const mainTranslationLink = displayTranslationOptions(null, preferredTranslationId);
            if (mainTranslationLink) {
                const startFrom = getStartFromValue(mainTranslationLink);
                loadPlayer(mainTranslationLink.link_pk, mainTranslationLink.translation_id.toString(), startFrom);
                // Highlight the corresponding button
                const mainTranslationButton = translationButtonsContainer?.querySelector(`.translation-btn[data-link-pk='${mainTranslationLink.link_pk}']`);
                highlightTranslationButton(mainTranslationButton);
            } else {
                // If no main links are available
                if (playerPlaceholder) playerPlaceholder.innerHTML = '<div class="text-center text-muted border rounded p-5">{% trans "Select a translation to start watching" %}</div>';
                highlightTranslationButton(null); // Ensure no button is highlighted
            }
            return; // Exit early for player_only mode
        }

        // Proceed for episode-based layouts
        console.log("Restore Watched State: Checking for last episode...");
        if (!LAST_EPISODE_KEY) {
            console.log("Restore Watched State: No episode key defined.");
            return;
        }

        const lastEpisodePk = localStorage.getItem(LAST_EPISODE_KEY);
        if (lastEpisodePk) {
            const lastEpisodeElement = findEpisodeElementByPk(lastEpisodePk);
            if (lastEpisodeElement) {
                console.log(`Restore Watched State: Restoring last watched episode: PK ${lastEpisodePk}`);
                // Find the season tab this episode belongs to
                const targetTabPaneId = lastEpisodeElement.closest('.tab-pane')?.id;
                const targetSeasonButton = targetTabPaneId ? document.querySelector(`button[data-bs-target='#${targetTabPaneId}']`) : null;

                // If the correct season tab is not active, activate it first
                if (targetSeasonButton && !targetSeasonButton.classList.contains('active')) {
                    console.log(`Restore Watched State: Activating season tab for episode ${lastEpisodePk}`);
                    try {
                        // Use 'shown.bs.tab' event to ensure tab content is visible before selecting episode
                        targetSeasonButton.addEventListener('shown.bs.tab', () => {
                            console.log(`Restore Watched State: Tab shown for ${targetTabPaneId}, selecting episode.`);
                            handleEpisodeSelection(lastEpisodeElement, false); // Select episode after tab is shown
                        }, {once: true}); // Ensure listener runs only once
                        new bootstrap.Tab(targetSeasonButton).show(); // Trigger tab change
                    } catch (e) {
                        console.error("Bootstrap tab error during restore:", e);
                        // Fallback if tab switch fails
                        handleEpisodeSelection(lastEpisodeElement, false);
                    }
                } else {
                    // If the tab is already active or not found, just select the episode
                    console.log(`Restore Watched State: Correct tab already active or button not found, selecting episode.`);
                    handleEpisodeSelection(lastEpisodeElement, false);
                }
            } else {
                console.log(`Restore Watched State: Could not find last watched episode element (PK ${lastEpisodePk}) in DOM.`);
                // Clear placeholder and translations if last episode not found
                if (playerPlaceholder) playerPlaceholder.innerHTML = '<div class="text-center text-muted border rounded p-5">{% trans "Select an episode to start watching" %}</div>';
                displayTranslationOptions(null, null); // Clear translation buttons
                highlightEpisode(null); // Clear episode highlight
            }
        } else {
            console.log("Restore Watched State: No last watched episode found in localStorage.");
            // Clear placeholder and translations if no last episode stored
            if (playerPlaceholder) playerPlaceholder.innerHTML = '<div class="text-center text-muted border rounded p-5">{% trans "Select an episode to start watching" %}</div>';
            displayTranslationOptions(null, null); // Clear translation buttons
            highlightEpisode(null); // Clear episode highlight
        }
    }


    function restoreLastDetailTab() {
        if (!LAST_DETAIL_TAB_KEY) return;
        const lastTabTarget = localStorage.getItem(LAST_DETAIL_TAB_KEY);
        const defaultTabSelector = '#details-pane';
        const targetSelector = lastTabTarget || defaultTabSelector;
        const tabButton = document.querySelector(`#detail-tabs button[data-bs-target="${targetSelector}"]`);

        if (tabButton && !tabButton.classList.contains('active')) {
            try {
                console.log(`Restoring detail tab: ${targetSelector}`);
                new bootstrap.Tab(tabButton).show();
            } catch (e) {
                console.error("Bootstrap Tab error on restore:", e);
            }
        } else if (!tabButton) {
            console.warn(`Could not find button for stored tab selector: ${targetSelector}. Falling back to default.`);
            const defaultTabButton = document.querySelector(`#detail-tabs button[data-bs-target="${defaultTabSelector}"]`);
            if (defaultTabButton && !defaultTabButton.classList.contains('active')) {
                try {
                    new bootstrap.Tab(defaultTabButton).show();
                } catch (e) {
                }
            }
        }
    }


    /**
     * Applies the selected layout (episodes_below, episodes_right, player_only)
     * by adjusting Bootstrap column classes and adding/removing helper classes.
     * @param {string} layout - The desired layout ('episodes_below', 'episodes_right', 'player_only').
     * @param {boolean} triggeredByInitialization - True if called during initial page load.
     */
    function applyLayoutPreference(layout, triggeredByInitialization = false) {
        console.log(`ApplyLayoutPreference called with layout: '${layout}', Initializing: ${triggeredByInitialization}`);
        if (!playerContainerColumn || !episodeListColumn || !watchAreaRow) {
            console.error("Layout columns or row not found in DOM!");
            return;
        }

        // --- Determine chosen layout ---
        const chosenLayout = LAYOUTS.includes(layout) ? layout : 'episodes_below'; // Default to 'below'
        console.log(`Chosen layout: '${chosenLayout}'`);

        // --- Avoid redundant application ---
        if (currentLayout === chosenLayout && !triggeredByInitialization) {
            console.log(`Layout '${chosenLayout}' is already active. Skipping redundant application.`);
            return;
        }

        const previousLayout = currentLayout;
        currentLayout = chosenLayout; // Update global state

        // --- Define Bootstrap classes and helper flags based on layout ---
        let playerColClasses = ['col-12']; // Default: Player takes full width
        let episodeColClasses = ['col-12']; // Default: Episodes take full width below
        let episodeHidden = false;
        let addScrollClass = false;
        let addListViewClass = false;
        let episodeMarginTop = 'mt-3'; // Default margin for 'below'

        switch (chosenLayout) {
            case 'episodes_right':
                playerColClasses = ['col-lg-9', 'col-md-12']; // Player: 9 cols on large, 12 on medium/small
                episodeColClasses = ['col-lg-3', 'col-md-12']; // Episodes: 3 cols on large, 12 on medium/small
                addScrollClass = true;     // Enable vertical scrolling for episode list
                addListViewClass = true;   // Add class for list styling
                episodeMarginTop = 'mt-3 mt-lg-0'; // Margin top on small screens, none on large
                break;
            case 'player_only':
                playerColClasses = ['col-12']; // Player takes full width
                episodeHidden = true;      // Hide episode column entirely
                episodeMarginTop = '';       // No margin needed if hidden
                break;
            case 'episodes_below':
                // Defaults are already set (col-12 for both)
                episodeMarginTop = 'mt-3'; // Standard margin when below
                break;
        }

        console.log(`Applying classes - Player: ${playerColClasses.join(' ')}, Episodes: ${episodeColClasses.join(' ')}, Hidden: ${episodeHidden}, Scroll: ${addScrollClass}, ListView: ${addListViewClass}, MarginTop: '${episodeMarginTop}'`);

        // --- Apply classes to columns ---
        // Reset existing column classes first (optional but safer)
        playerContainerColumn.className = ''; // Clear all classes
        episodeListColumn.className = '';   // Clear all classes

        // Add base 'col-12' and then specific layout classes
        playerContainerColumn.classList.add('col-12', ...playerColClasses);
        episodeListColumn.classList.add('col-12', ...episodeColClasses);

        // --- Handle visibility and margins ---
        if (episodeHidden) {
            episodeListColumn.classList.add('d-none');
        } else {
            episodeListColumn.classList.remove('d-none');
            // Apply margin top classes
            if (episodeMarginTop) {
                episodeMarginTop.split(' ').forEach(cls => episodeListColumn.classList.add(cls));
            }
        }

        // --- Apply helper classes ---
        if (addScrollClass) {
            episodeListColumn.classList.add(SCROLL_CLASS);
        } else {
            episodeListColumn.classList.remove(SCROLL_CLASS);
        }

        if (addListViewClass) {
            episodeListColumn.classList.add(LIST_VIEW_CLASS);
        } else {
            episodeListColumn.classList.remove(LIST_VIEW_CLASS);
        }

        // --- Persist preference and update UI ---
        localStorage.setItem(PLAYER_LAYOUT_KEY, chosenLayout);
        console.log(`Saved preference to localStorage: ${chosenLayout}`);
        layoutRadios.forEach(radio => {
            radio.checked = (radio.value === chosenLayout);
        });

        updateNavButtons(); // Update prev/next buttons based on new layout

        // --- Handle transitions between layouts ---
        if (previousLayout !== chosenLayout) {
            console.log(`Layout changed from '${previousLayout}' to '${chosenLayout}'`);
            if (chosenLayout === 'player_only') {
                console.log("Transitioning to player_only mode...");
                highlightEpisode(null); // Deselect any episode
                const preferredTranslationId = currentSelectedTranslationId || (LAST_TRANSLATION_KEY ? localStorage.getItem(LAST_TRANSLATION_KEY) : null);
                const mainTranslationLink = displayTranslationOptions(null, preferredTranslationId); // Show main translations
                if (mainTranslationLink) {
                    const startFrom = getStartFromValue(mainTranslationLink);
                    loadPlayer(mainTranslationLink.link_pk, mainTranslationLink.translation_id.toString(), startFrom);
                    const mainTranslationButton = translationButtonsContainer?.querySelector(`.translation-btn[data-link-pk='${mainTranslationLink.link_pk}']`);
                    highlightTranslationButton(mainTranslationButton);
                } else { // If no main links found
                    if (playerPlaceholder) playerPlaceholder.innerHTML = '<div class="text-center text-muted border rounded p-5">{% trans "Select a translation to start watching" %}</div>';
                    highlightTranslationButton(null);
                }
            } else if (previousLayout === 'player_only') {
                console.log("Transitioning from player_only mode...");
                // Try to restore the last watched episode
                const lastEpisodePk = LAST_EPISODE_KEY ? localStorage.getItem(LAST_EPISODE_KEY) : null;
                const lastEpisodeElement = lastEpisodePk ? findEpisodeElementByPk(lastEpisodePk) : null;
                if (lastEpisodeElement) {
                    handleEpisodeSelection(lastEpisodeElement, false); // Reloads player & translations for the episode
                } else { // If no episode was previously watched or found
                    if (playerPlaceholder) playerPlaceholder.innerHTML = '<div class="text-center text-muted border rounded p-5">{% trans "Select an episode to start watching" %}</div>';
                    displayTranslationOptions(null, null); // Clear translations
                    highlightEpisode(null);
                    highlightTranslationButton(null);
                }
            } else {
                // Transition between 'below' and 'right' - usually no player reload needed
                // Ensure episode highlight is maintained if an episode was selected
                if (currentEpisodeElement) {
                    highlightEpisode(currentEpisodeElement); // Re-apply highlight (might be needed if classes changed)
                    // Re-display translations for the current episode if needed? Generally not required unless DOM changed drastically.
                    // displayTranslationOptions(currentEpisodeElement.dataset.episodePk, currentSelectedTranslationId);
                } else {
                    // If no episode is selected, clear translations
                    displayTranslationOptions(null, null);
                }
            }
        } else {
            console.log(`Layout '${chosenLayout}' was already set, no transition logic needed.`);
        }
    }


    function initializeLayout() {
        console.log("Initializing layout...");
        const storedLayout = localStorage.getItem(PLAYER_LAYOUT_KEY);
        console.log("Stored layout from localStorage:", storedLayout);
        let layoutToApply = storedLayout || 'episodes_below'; // Default

        // Check if player_only option is disabled, and default to 'below' if it is
        if (layoutToApply === 'player_only' && playerOnlyRadio?.disabled) {
            layoutToApply = 'episodes_below';
            console.log("Player_only layout disabled, falling back to episodes_below for initialization.");
        }
        console.log("Layout to apply on initialization:", layoutToApply);
        applyLayoutPreference(layoutToApply, true); // Apply layout, marking as initialization
    }


    function checkPlayerOnlyAvailability() {
        // Check if the mainLinksData object has any keys
        const hasMainLinks = Object.keys(mainLinksData).length > 0;
        if (!hasMainLinks && playerOnlyRadio && playerOnlyLabel) {
            console.log("Disabling player_only layout option: No main links found.");
            playerOnlyRadio.disabled = true;
            playerOnlyLabel.classList.add('disabled', 'opacity-50');
            // Use JS to set the title for disabled state
            playerOnlyLabel.setAttribute('title', '{% trans "Player only option unavailable (no main item link found)" %}');
            // Optionally re-enable tooltips if using Bootstrap's JS tooltips
            // const tooltipInstance = bootstrap.Tooltip.getInstance(playerOnlyLabel);
            // if (tooltipInstance) { tooltipInstance.setContent({ '.tooltip-inner': 'New Title' }); }
        } else if (playerOnlyRadio && playerOnlyLabel) {
            // Ensure it's enabled if links exist
            playerOnlyRadio.disabled = false;
            playerOnlyLabel.classList.remove('disabled', 'opacity-50');
            playerOnlyLabel.setAttribute('title', '{% trans "Player only (hide episodes)" %}');
            // Update tooltip content if necessary
        }
    }


    // --- Event Listeners ---
    if (episodesContainer) {
        // Use event delegation on the container for episode clicks
        episodesContainer.addEventListener('click', (event) => {
            const episodeCard = event.target.closest('.episode-selector');
            // Process click only if not in player_only mode
            if (episodeCard && currentLayout !== 'player_only') {
                event.preventDefault();
                handleEpisodeSelection(episodeCard, true); // Mark as manual click
            }
        });
    }

    // Use event delegation on the buttons container for translation clicks
    if (translationButtonsContainer) {
        translationButtonsContainer.addEventListener('click', (event) => {
            const translationButton = event.target.closest('.translation-btn');
            if (translationButton) {
                event.preventDefault();
                const linkPk = translationButton.dataset.linkPk;
                const translationId = translationButton.dataset.translationId;
                // Get start_from attribute, default to null if missing or invalid
                const startFrom = parseInt(translationButton.dataset.startFrom, 10) || null;

                if (linkPk && translationId) {
                    highlightTranslationButton(translationButton); // Highlight clicked button
                    loadPlayer(linkPk, translationId, startFrom); // Load player with link PK, translation ID, and start time
                } else {
                    console.error("Translation button clicked but no link PK or translation ID found.");
                }
            }
        });
    }

    if (nextEpisodeBtn) {
        nextEpisodeBtn.addEventListener('click', () => {
            // Allow action only if not in player_only mode
            if (currentLayout !== 'player_only') {
                const nextElement = findNextEpisodeElement(currentEpisodeElement);
                if (nextElement) {
                    handleEpisodeSelection(nextElement, true);
                }
            }
        });
    }

    if (prevEpisodeBtn) {
        prevEpisodeBtn.addEventListener('click', () => {
            // Allow action only if not in player_only mode
            if (currentLayout !== 'player_only') {
                const prevElement = findPrevEpisodeElement(currentEpisodeElement);
                if (prevElement) {
                    handleEpisodeSelection(prevElement, true);
                }
            }
        });
    }

    // Listener for main detail tabs ('Details', 'Watch')
    const detailTabs = document.querySelectorAll('#detail-tabs button[data-bs-toggle="tab"]');
    detailTabs.forEach(tabButton => {
        tabButton.addEventListener('shown.bs.tab', event => {
            if (LAST_DETAIL_TAB_KEY) {
                const activeTabTarget = event.target.getAttribute('data-bs-target');
                if (activeTabTarget) {
                    localStorage.setItem(LAST_DETAIL_TAB_KEY, activeTabTarget);
                    console.log(`Saved active detail tab: ${activeTabTarget}`);
                }
            }
        });
    });

    // Listener for player layout radio buttons
    layoutRadios.forEach(radio => {
        radio.addEventListener('change', (event) => {
            console.log(`Layout radio changed: ID='${event.target.id}', Value='${event.target.value}', Checked=${event.target.checked}`);
            if (event.target.checked) {
                applyLayoutPreference(event.target.value, false); // Apply selected layout, not initialization
            }
        });
    });

    // --- Initializations ---
    console.log("Media detail handler initializing...");
    episodesLinksData = parseJsonData(episodesLinksDataElement, 'Episodes links');
    mainLinksData = parseJsonData(mainLinksDataElement, 'Main links');
    checkPlayerOnlyAvailability(); // Check if main links exist to enable/disable option
    initializeLayout();           // Apply the stored or default layout
    restoreLastDetailTab();       // Activate the last used detail tab
    // Delay state restoration slightly to ensure layout/tabs are settled
    setTimeout(() => {
        restoreLastWatchedState();    // Load last watched episode/translation based on layout
    }, 50); // 50ms delay, adjust if needed
    updateNavButtons(); // Update prev/next buttons visibility based on initial layout
    console.log("Media detail handler initialization complete.");

}); // End DOMContentLoaded