(() => {
    const form = document.getElementById('contact-form');
    const status = document.getElementById('form-status');
    const button = form.querySelector('button[type="submit"]');
    const endpoint = window.SALESFORCE_CONTACT_ENDPOINT;
    let submitting = false;
    const attribution = {};
    const params = new URLSearchParams(window.location.search);
    for (const key of ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term']) {
        if (params.has(key)) attribution[key] = params.get(key).slice(0, 200);
    }

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        if (submitting) return;
        for (const id of ['fullName', 'email', 'company', 'message']) {
            form.elements.namedItem(id).value = form.elements.namedItem(id).value.trim();
        }
        if (!form.reportValidity()) return;
        if (!endpoint) {
            status.textContent = 'The form is temporarily unavailable. Please email michael@horustech.dev.';
            return;
        }
        submitting = true;
        button.disabled = true;
        button.textContent = 'Sending...';
        form.setAttribute('aria-busy', 'true');
        status.textContent = 'Sending your request...';
        const data = new FormData(form);
        try {
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                signal: AbortSignal.timeout(20000),
                body: JSON.stringify({
                    name: data.get('fullName'),
                    email: data.get('email'),
                    company: data.get('company'),
                    subject: data.get('interest'),
                    message: data.get('message'),
                    website: data.get('website'),
                    attribution,
                }),
            });
            const result = await response.json();
            if (!response.ok || !result.contactId) throw new Error('Request not confirmed');
            status.textContent = `Your request was received. Reference: ${result.contactId}. We will follow up by email.`;
            form.reset();
        } catch (error) {
            status.textContent = error.name === 'TimeoutError'
                ? 'We could not confirm receipt in time. Your details are still here. Please email michael@horustech.dev before resubmitting.'
                : 'We could not confirm receipt. Your details are still here. Please try again or email michael@horustech.dev.';
        } finally {
            submitting = false;
            button.disabled = false;
            button.textContent = 'Get Free Assessment';
            form.removeAttribute('aria-busy');
        }
    });
})();
