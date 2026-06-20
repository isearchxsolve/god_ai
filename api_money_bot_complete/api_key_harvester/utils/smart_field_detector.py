"""
Smart Field Detector
====================
Uses JavaScript to extract all visible inputs, their labels (programmatic + visual proximity),
and match them to known field types. No OCR needed — reads label text directly from DOM.
"""
from typing import Dict, Optional, List, Tuple


class SmartFieldDetector:
    """
    Detects form fields by reading labels, placeholders, aria attributes, and nearby text
    for every visible input on the page. More comprehensive than DynamicFieldFinder
    because it captures visually-associated label text via JS.
    """

    FIELD_PATTERNS = {
        "email": ["email", "e-mail", "mail"],
        "password": ["password", "passwd", "pwd"],
        "first_name": ["first name", "first", "given name", "fname", "forename"],
        "last_name": ["last name", "last", "surname", "family name", "lname"],
        "full_name": ["full name", "name", "your name", "display name"],
        "username": ["username", "user name", "user", "handle", "login"],
        "phone": ["phone", "telephone", "tel", "mobile", "cell"],
        "country": ["country", "nation", "region"],
        "city": ["city", "town", "locality"],
        "state": ["state", "province", "region"],
        "zip": ["zip", "zip code", "postal", "postcode", "post code"],
        "address": ["address", "street", "addr"],
        "company": ["company", "organization", "org", "business", "employer"],
        "website": ["website", "url", "site", "web"],
        "code": ["code", "otp", "verification code", "mfa", "2fa", "token"],
        "agree": ["agree", "terms", "accept", "consent", "toc"],
    }

    @classmethod
    def find_all_fields(cls, page) -> List[Dict]:
        """Use JS to find all visible inputs with their associated labels and metadata."""
        return page.evaluate("""() => {
            const inputs = document.querySelectorAll('input, select, textarea');
            const results = [];
            
            inputs.forEach(el => {
                // Skip hidden elements
                const rect = el.getBoundingClientRect();
                if (rect.width === 0 || rect.height === 0) return;
                
                // Check if visible
                const style = window.getComputedStyle(el);
                if (style.display === 'none' || style.visibility === 'hidden') return;
                
                // Gather metadata
                const type = el.getAttribute('type') || el.tagName.toLowerCase();
                const name = el.getAttribute('name') || '';
                const id = el.getAttribute('id') || '';
                const placeholder = el.getAttribute('placeholder') || '';
                const ariaLabel = el.getAttribute('aria-label') || '';
                const autocomplete = el.getAttribute('autocomplete') || '';
                const testid = el.getAttribute('data-testid') || el.getAttribute('data-test') || '';
                const className = el.getAttribute('class') || '';
                
                // Find associated label
                let labelText = '';
                
                // Method 1: aria-labelledby
                const labelledby = el.getAttribute('aria-labelledby');
                if (labelledby) {
                    const labelEl = document.getElementById(labelledby);
                    if (labelEl) labelText = labelEl.textContent.trim();
                }
                
                // Method 2: id -> label[for]
                if (!labelText && id) {
                    const labelFor = document.querySelector(`label[for="${CSS.escape(id)}"]`);
                    if (labelFor) labelText = labelFor.textContent.trim();
                }
                
                // Method 3: Wrapping label
                if (!labelText) {
                    const parent = el.closest('label');
                    if (parent) labelText = parent.textContent.trim();
                }
                
                // Method 4: Closest label-like element
                if (!labelText) {
                    const parent = el.parentElement;
                    if (parent) {
                        const labels = parent.querySelectorAll('label, span, div.label');
                        for (const lbl of labels) {
                            const txt = lbl.textContent.trim();
                            if (txt && txt.length < 100) {
                                labelText = txt;
                                break;
                            }
                        }
                    }
                }
                
                // Method 5: Previous sibling text
                if (!labelText) {
                    let prev = el.previousElementSibling;
                    while (prev) {
                        const txt = prev.textContent.trim();
                        if (txt) {
                            labelText = txt;
                            break;
                        }
                        prev = prev.previousElementSibling;
                    }
                }
                
                // Clean label text
                labelText = labelText.replace(/[\\s]+/g, ' ').trim();
                if (labelText.includes('*')) labelText = labelText.replace('*', '').trim();
                
                results.push({
                    type,
                    name,
                    id,
                    placeholder,
                    ariaLabel,
                    autocomplete,
                    testid,
                    className,
                    labelText,
                    isSelect: el.tagName === 'SELECT',
                    isCheckbox: type === 'checkbox',
                    rect: { x: rect.x, y: rect.y, w: rect.width, h: rect.height }
                });
            });
            
            return results;
        }""")

    @classmethod
    def classify_field(cls, field_info: Dict) -> Optional[str]:
        """Given a field info dict, return the best matching field type or None."""
        texts = []
        if field_info.get("labelText"):
            texts.append(field_info["labelText"].lower())
        if field_info.get("placeholder"):
            texts.append(field_info["placeholder"].lower())
        if field_info.get("ariaLabel"):
            texts.append(field_info["ariaLabel"].lower())
        if field_info.get("name"):
            texts.append(field_info["name"].lower())
        if field_info.get("autocomplete"):
            texts.append(field_info["autocomplete"].lower())
        if field_info.get("testid"):
            texts.append(field_info["testid"].lower())
        if field_info.get("id"):
            texts.append(field_info["id"].lower())

        combined = " ".join(texts)

        for field_type, patterns in cls.FIELD_PATTERNS.items():
            for pat in patterns:
                if pat in combined:
                    return field_type
        return None

    @classmethod
    def fill_all(cls, page, values: Dict[str, str]) -> Dict[str, bool]:
        """
        Fill all detected form fields with appropriate values.
        values is a dict mapping field_type -> value.
        Returns dict of field_type -> whether it was filled.
        """
        fields = cls.find_all_fields(page)
        results = {}
        for field in fields:
            if field["isCheckbox"]:
                continue
            field_type = cls.classify_field(field)
            if field_type and field_type in values:
                try:
                    # Build a selector for this specific field — escape special chars in JS
                    sel = page.evaluate("""(field) => {
                        const cssEscape = (s) => CSS.escape ? CSS.escape(s) : s.replace(/([!"#$%&'()*+,./:;<=>?@[\\]^`{|}~])/g, '\\\\$1');
                        if (field.id) return '#' + cssEscape(field.id);
                        if (field.name) return '[name="' + field.name.replace(/"/g, '\\"') + '"]';
                        return null;
                    }""", field)
                    if not sel:
                        continue
                    el = page.query_selector(sel)
                    if el:
                        if field["isSelect"]:
                            try:
                                el.select_option(label=values[field_type])
                            except Exception:
                                el.select_option(index=1)
                        else:
                            el.fill(values[field_type])
                        results[field_type] = True
                except Exception:
                    results[field_type] = False
        return results
