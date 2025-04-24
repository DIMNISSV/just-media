// catalog/static/catalog/js/media_detail_handler.js
document.addEventListener('DOMContentLoaded', () => {
    const playerPlaceholder = document.getElementById('player-placeholder');
    const mediaDescription = document.getElementById('media-description');
    const episodesContainer = document.getElementById('seasons-tab-content');
    const nextEpisodeBtn = document.getElementById('next-episode-btn');
    const prevEpisodeBtn = document.getElementById('prev-episode-btn');
    const playerUrlTemplate = document.getElementById('player-url-template')?.dataset.url;
    const translationSelectorPlaceholder = document.getElementById('translation-selector-placeholder');
    const episodesLinksDataElement = document.getElementById('episodes-links-data');
    const mediaPk = episodesContainer?.dataset.mediaPk;

    let episodesLinksData = {};
    try {
        if (episodesLinksDataElement) {
            episodesLinksData = JSON.parse(episodesLinksDataElement.textContent || '{}');
        }
    } catch (e) {
        console.error("Error parsing episodes links data:", e);
    }

    let currentEpisodeElement = null;
    let currentSelectedTranslationId = null; // Stores the ID (e.g., 704) of the last *selected* translation

    const lastEpisodeKey = mediaPk ? `last_watched_episode_${mediaPk}` : null;
    const lastTranslationKey = mediaPk ? `last_selected_translation_${mediaPk}` : null; // Will store the translation ID

    console.log("Media detail handler loaded. Media PK:", mediaPk);

    function generatePlayerUrl(linkPk) {
        if (!playerUrlTemplate || !linkPk) return null;
        return playerUrlTemplate.replace('/0/', `/${linkPk}/`);
    }

    function loadPlayer(linkPk, translationIdToSave) {
        const playerUrl = generatePlayerUrl(linkPk);
        console.log(`Attempting to load player for link PK: ${linkPk}, Translation ID: ${translationIdToSave}, URL: ${playerUrl}`);
        if (playerUrl && playerPlaceholder) {
            playerPlaceholder.innerHTML = `
                <div class="player-container" style="position: relative; padding-bottom: 56.25%; height: 0; overflow: hidden; max-width: 100%; background: #000;">
                    <iframe src="${playerUrl}"
                            style="position: absolute; top: 0; left: 0; width: 100%; height: 100%;"
                            frameborder="0" scrolling="no" allowfullscreen="allowfullscreen"
                            webkitallowfullscreen="webkitallowfullscreen" mozallowfullscreen="mozallowfullscreen"
                            loading="lazy">
                    </iframe>
                </div>`;
            if (mediaDescription) {
                mediaDescription.style.display = 'none';
            }

            // Save episode PK and the *selected* translation ID
            if (currentEpisodeElement && lastEpisodeKey) {
                const episodePk = currentEpisodeElement.dataset.episodePk;
                localStorage.setItem(lastEpisodeKey, episodePk);
                console.log(`Saved last episode PK: ${episodePk} to ${lastEpisodeKey}`);
            }
            if (translationIdToSave && lastTranslationKey) {
                localStorage.setItem(lastTranslationKey, translationIdToSave);
                console.log(`Saved last translation ID: ${translationIdToSave} to ${lastTranslationKey}`);
                currentSelectedTranslationId = translationIdToSave; // Update global state
            }

        } else {
            console.error('Could not generate player URL or placeholder not found.');
            playerPlaceholder.innerHTML = '<p class="text-danger">Error loading player.</p>';
        }
    }

    function displayTranslationOptions(episodePk, preferredTranslationId = null) {
        if (!translationSelectorPlaceholder) return null; // Return null if placeholder doesn't exist

        const links = episodesLinksData[episodePk] || [];
        console.log(`Translations found for episode PK ${episodePk}:`, links);

        let buttonsHtml = '';
        let translationToAutoLoad = null; // Store the whole link object

        if (links.length > 0) {
            buttonsHtml = '<span class="me-2">Choose translation:</span>'; // i18n needed

            let preferredLink = null;
            let firstLink = links[0]; // Keep track of the first link as a fallback

            // Find the preferred link or use the first one
            if (preferredTranslationId) {
                preferredLink = links.find(link => link.translation_id == preferredTranslationId);
            }
            translationToAutoLoad = preferredLink || firstLink; // Select preferred or fallback to first

            links.forEach(link => {
                const quality = link.quality ? `(${link.quality})` : '';
                // Check if this link is the one we decided to autoload
                const isSelected = translationToAutoLoad && link.link_pk === translationToAutoLoad.link_pk;
                const btnClass = isSelected ? 'btn-primary active' : 'btn-outline-primary';

                buttonsHtml += `
                    <button class="btn btn-sm ${btnClass} me-1 mb-1 translation-btn"
                            data-link-pk="${link.link_pk}"
                            data-translation-id="${link.translation_id}">
                        ${link.translation_title} ${quality}
                    </button>`;
            });
            translationSelectorPlaceholder.innerHTML = buttonsHtml;
        } else {
            translationSelectorPlaceholder.innerHTML = '<span class="text-warning">No translations found for this episode.</span>'; // i18n needed
            playerPlaceholder.innerHTML = ''; // Clear player placeholder
        }
        // Return the link object to autoload, or null
        return translationToAutoLoad;
    }

    function highlightEpisode(episodeElement) {
        if (currentEpisodeElement) {
            currentEpisodeElement.classList.remove('border', 'border-primary', 'border-3');
        }
        if (episodeElement) {
            episodeElement.classList.add('border', 'border-primary', 'border-3');
            currentEpisodeElement = episodeElement;
            updateNavButtons();
        } else {
            currentEpisodeElement = null;
            updateNavButtons();
        }
    }

    function highlightTranslationButton(buttonElement) {
        translationSelectorPlaceholder.querySelectorAll('.translation-btn.active').forEach(btn => {
            btn.classList.remove('active');
            btn.classList.replace('btn-primary', 'btn-outline-primary');
        });
        if (buttonElement) {
            buttonElement.classList.add('active');
            buttonElement.classList.replace('btn-outline-primary', 'btn-primary');
        }
    }

    function findEpisodeElementByPk(episodePk) {
        if (!episodesContainer || !episodePk) return null;
        return episodesContainer.querySelector(`.episode-selector[data-episode-pk='${episodePk}']`);
    }

    function findEpisodeElement(seasonNum, episodeNum) {
        if (!episodesContainer) return null;
        return episodesContainer.querySelector(`.episode-selector[data-season-num='${seasonNum}'][data-episode-num='${episodeNum}']`);
    }

    function findNextEpisodeElement(currentElement) {
        if (!currentElement) return null;
        const currentContainer = currentElement.closest('.episodes-grid');
        if (!currentContainer) return null;

        const nextSibling = currentElement.closest('.col').nextElementSibling;
        if (nextSibling && nextSibling.querySelector('.episode-selector')) {
            return nextSibling.querySelector('.episode-selector');
        } else {
            const currentTabPane = currentElement.closest('.tab-pane');
            if (!currentTabPane) return null;
            const nextTabPane = currentTabPane.nextElementSibling;
            if (nextTabPane && nextTabPane.classList.contains('tab-pane')) {
                const nextTabButtonId = nextTabPane.getAttribute('aria-labelledby');
                const nextTabButton = document.getElementById(nextTabButtonId);
                if (nextTabButton) {
                    try {
                        new bootstrap.Tab(nextTabButton).show();
                    } catch (e) {
                        console.error("Bootstrap Tab error:", e);
                    }
                }
                return nextTabPane.querySelector('.episode-selector');
            }
        }
        return null;
    }

    function findPrevEpisodeElement(currentElement) {
        if (!currentElement) return null;
        const currentContainer = currentElement.closest('.episodes-grid');
        if (!currentContainer) return null;

        const prevSibling = currentElement.closest('.col').previousElementSibling;
        if (prevSibling && prevSibling.querySelector('.episode-selector')) {
            return prevSibling.querySelector('.episode-selector');
        } else {
            const currentTabPane = currentElement.closest('.tab-pane');
            if (!currentTabPane) return null;
            const prevTabPane = currentTabPane.previousElementSibling;
            if (prevTabPane && prevTabPane.classList.contains('tab-pane')) {
                const prevTabButtonId = prevTabPane.getAttribute('aria-labelledby');
                const prevTabButton = document.getElementById(prevTabButtonId);
                if (prevTabButton) {
                    try {
                        new bootstrap.Tab(prevTabButton).show();
                    } catch (e) {
                        console.error("Bootstrap Tab error:", e);
                    }
                }
                const episodesInPrev = prevTabPane.querySelectorAll('.episode-selector');
                return episodesInPrev.length > 0 ? episodesInPrev[episodesInPrev.length - 1] : null;
            }
        }
        return null;
    }

    function updateNavButtons() {
        const nextElement = findNextEpisodeElement(currentEpisodeElement);
        const prevElement = findPrevEpisodeElement(currentEpisodeElement);
        if (nextEpisodeBtn) nextEpisodeBtn.disabled = !nextElement;
        if (prevEpisodeBtn) prevEpisodeBtn.disabled = !prevElement;
    }

    function handleEpisodeSelection(episodeElement, manuallyClicked = false) {
        if (!episodeElement) return;

        const episodePk = episodeElement.dataset.episodePk;
        highlightEpisode(episodeElement);

        // Get preferred translation ID from storage, or null if none
        const preferredTranslationId = lastTranslationKey ? localStorage.getItem(lastTranslationKey) : null;

        // Display translation options, pre-selecting preferred/first if available
        // This function now returns the link object to autoload, or null
        const translationLinkToLoad = displayTranslationOptions(episodePk, preferredTranslationId);

        // Automatically load player ONLY if a translation was pre-selected (preferred found or first available)
        if (translationLinkToLoad) {
            console.log(`Autoloading player for episode ${episodePk} with translation ID ${translationLinkToLoad.translation_id}`);
            loadPlayer(translationLinkToLoad.link_pk, translationLinkToLoad.translation_id.toString());
            // Ensure the button is highlighted
            const translationButton = translationSelectorPlaceholder?.querySelector(`.translation-btn[data-link-pk='${translationLinkToLoad.link_pk}']`);
            highlightTranslationButton(translationButton);
        } else {
            // Clear player and reset selected translation if no options or no preference match
            playerPlaceholder.innerHTML = '<div class="text-center text-muted border rounded p-5">Select a translation</div>'; // i18n needed
            currentSelectedTranslationId = null;
            if (mediaDescription && manuallyClicked) { // Show description only if user manually clicked episode
                mediaDescription.style.display = 'block';
            }
        }
    }

    function restoreLastWatchedState() {
        if (!lastEpisodeKey) return;

        const lastEpisodePk = localStorage.getItem(lastEpisodeKey);
        if (lastEpisodePk) {
            const lastEpisodeElement = findEpisodeElementByPk(lastEpisodePk);
            if (lastEpisodeElement) {
                console.log(`Restoring last watched episode: PK ${lastEpisodePk}`);
                const targetTabPaneId = lastEpisodeElement.closest('.tab-pane')?.id;
                const targetTabButton = targetTabPaneId ? document.querySelector(`button[data-bs-target='#${targetTabPaneId}']`) : null;
                if (targetTabButton) {
                    try {
                        new bootstrap.Tab(targetTabButton).show();
                    } catch (e) {
                        console.error("Bootstrap Tab error:", e);
                    }
                }

                // Select episode, display translations, and autoload player if possible
                handleEpisodeSelection(lastEpisodeElement, false); // Pass false for manuallyClicked

            } else {
                console.log(`Could not find last watched episode element (PK ${lastEpisodePk}) in DOM.`);
            }
        } else {
            console.log("No last watched episode found in localStorage.");
        }
    }


    // --- Event Listeners ---
    if (episodesContainer) {
        episodesContainer.addEventListener('click', (event) => {
            const episodeCard = event.target.closest('.episode-selector');
            if (episodeCard) {
                event.preventDefault();
                handleEpisodeSelection(episodeCard, true); // Pass true for manuallyClicked
            }
        });
    }

    if (translationSelectorPlaceholder) {
        translationSelectorPlaceholder.addEventListener('click', (event) => {
            const translationButton = event.target.closest('.translation-btn');
            if (translationButton) {
                event.preventDefault();
                const linkPk = translationButton.dataset.linkPk;
                const translationId = translationButton.dataset.translationId; // Get the ID to save

                if (linkPk) {
                    highlightTranslationButton(translationButton); // Highlight chosen button
                    loadPlayer(linkPk, translationId); // Load player and save this translation ID
                } else {
                    console.error("Translation button clicked but no link PK found.");
                }
            }
        });
    }


    if (nextEpisodeBtn) {
        nextEpisodeBtn.addEventListener('click', () => {
            const nextElement = findNextEpisodeElement(currentEpisodeElement);
            if (nextElement) {
                handleEpisodeSelection(nextElement, true);
            } // Use handler
        });
    }

    if (prevEpisodeBtn) {
        prevEpisodeBtn.addEventListener('click', () => {
            const prevElement = findPrevEpisodeElement(currentEpisodeElement);
            if (prevElement) {
                handleEpisodeSelection(prevElement, true);
            } // Use handler
        });
    }

    updateNavButtons();
    restoreLastWatchedState();

}); // End DOMContentLoaded