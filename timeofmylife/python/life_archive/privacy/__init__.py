"""Privacy engine for Life Archive.

Implements the privacy classification and redaction system as specified in
Section 25 of the master mission. The privacy engine ensures that:
- Everything is PRIVATE by default
- Third-party private information is never automatically public
- Credentials, tokens, passwords, and secrets never enter the research corpus
- No automatic public publishing occurs
- Human approval is required for all publication

The engine operates at multiple levels:
1. Classification: Assign privacy levels to all ingested data
2. Redaction: Remove PII before LLM prompts/embeddings
3. Tokenization: Replace sensitive data with reversible tokens
4. Consent tracking: Track permissions for third-party data
"""

import re
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Pattern, Set, Union
from urllib.parse import urlparse

from pydantic import BaseModel

from life_archive.schemas.provenance import PrivacyClassification


class PiiType(Enum):
    """Types of personally identifiable information that need protection."""

    EMAIL = "email"
    PHONE = "phone"
    ADDRESS = "address"
    NAME = "name"
    USERNAME = "username"
    ORGANIZATION = "organization"
    LOCATION = "location"
    DATE = "date"
    ID_NUMBER = "id_number"
    FINANCIAL = "financial"
    HEALTH = "health"
    CREDENTIAL = "credential"
    IP_ADDRESS = "ip_address"
    DEVICE_ID = "device_id"


class PrivacyRule(BaseModel):
    """A rule for classifying or redacting privacy-sensitive information."""

    id: str
    description: str
    pattern: str  # Regex pattern
    pii_type: PiiType
    classification: PrivacyClassification
    confidence_threshold: float = 0.9  # 0.0-1.0, default 90% confidence
    context_required: bool = False  # Whether context is needed for accurate detection


class PrivacyToken(BaseModel):
    """A token representing redacted sensitive information."""

    original_value: str
    token: str
    pii_type: PiiType
    classification: PrivacyClassification
    context: Dict[str, Any] = {}
    created_at: datetime = datetime.utcnow()


class PrivacyEngine:
    """Privacy classification and redaction engine."""

    def __init__(self):
        """Initialize the privacy engine with common rules."""
        self.rules = self._initialize_rules()
        self.token_store: Dict[str, PrivacyToken] = {}
        self.token_counter = 0

    def _initialize_rules(self) -> List[PrivacyRule]:
        """Initialize common privacy rules."""
        return [
            # Email addresses
            PrivacyRule(
                id="email_detection",
                description="Email address detection",
                pattern=r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
                pii_type=PiiType.EMAIL,
                classification=PrivacyClassification.THIRD_PARTY_PRIVATE,
            ),
            # Phone numbers (various formats)
            PrivacyRule(
                id="phone_detection",
                description="Phone number detection",
                pattern=r"\b(?:\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})\b",
                pii_type=PiiType.PHONE,
                classification=PrivacyClassification.THIRD_PARTY_PRIVATE,
            ),
            # IP addresses
            PrivacyRule(
                id="ip_detection",
                description="IP address detection",
                pattern=r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b",
                pii_type=PiiType.IP_ADDRESS,
                classification=PrivacyClassification.SENSITIVE,
            ),
            # Credit card numbers
            PrivacyRule(
                id="credit_card_detection",
                description="Credit card number detection",
                pattern=r"\b(?:\d{4}[-\s]?){3}\d{4}\b|\b\d{4}\s\d{4}\s\d{4}\s\d{4}\b",
                pii_type=PiiType.FINANCIAL,
                classification=PrivacyClassification.SENSITIVE,
            ),
            # Social Security Numbers (US format)
            PrivacyRule(
                id="ssn_detection",
                description="Social Security Number detection",
                pattern=r"\b\d{3}-\d{2}-\d{4}\b",
                pii_type=PiiType.ID_NUMBER,
                classification=PrivacyClassification.SENSITIVE,
            ),
            # Password patterns
            PrivacyRule(
                id="password_detection",
                description="Password-related text detection",
                pattern=r"\b(?:password|passphrase|passwd|pwd|secret|token|api[_-]?key)\b",
                pii_type=PiiType.CREDENTIAL,
                classification=PrivacyClassification.RESTRICTED,
            ),
            # Common credential file extensions
            PrivacyRule(
                id="credential_file_detection",
                description="Credential file detection",
                pattern=r"\.(?:key|pem|p12|pfx|pkcs12|jks|keystore|env|creds?|config|secret|token)s?\b",
                pii_type=PiiType.CREDENTIAL,
                classification=PrivacyClassification.RESTRICTED,
            ),
        ]

    def classify_content(
        self, content: Union[str, bytes], source_context: Optional[Dict] = None
    ) -> PrivacyClassification:
        """Classify content based on privacy rules.

        Args:
            content: Content to classify
            source_context: Context about the source (optional)

        Returns:
            Privacy classification
        """
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="ignore")

        highest_classification = PrivacyClassification.PRIVATE

        for rule in self.rules:
            pattern = re.compile(rule.pattern, re.IGNORECASE)
            matches = pattern.findall(content)

            if matches:
                # Update classification if this rule has higher sensitivity
                if self._is_higher_privacy(highest_classification, rule.classification):
                    highest_classification = rule.classification

        return highest_classification

    def redact_content(
        self, content: Union[str, bytes], classification_threshold: PrivacyClassification = PrivacyClassification.THIRD_PARTY_PRIVATE
    ) -> str:
        """Redact privacy-sensitive information from content.

        Args:
            content: Content to redact
            classification_threshold: Minimum classification level to redact

        Returns:
            Redacted content with sensitive information removed/replaced
        """
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="ignore")

        for rule in self.rules:
            # Only redact if rule classification meets threshold
            if self._is_higher_privacy(classification_threshold, rule.classification) or classification_threshold == rule.classification:
                pattern = re.compile(rule.pattern, re.IGNORECASE)
                
                def replace_match(match):
                    matched_text = match.group(0)
                    token = self._generate_token(matched_text, rule.pii_type, rule.classification)
                    return f"[REDACTED_{rule.pii_type.value.upper()}_{token.token}]"
                
                content = pattern.sub(replace_match, content)

        return content

    def tokenize_content(
        self, content: Union[str, bytes], classification_threshold: PrivacyClassification = PrivacyClassification.THIRD_PARTY_PRIVATE
    ) -> tuple[str, List[PrivacyToken]]:
        """Tokenize privacy-sensitive information in content.

        Unlike redaction, tokenization allows for reversible replacement.

        Args:
            content: Content to tokenize
            classification_threshold: Minimum classification level to tokenize

        Returns:
            Tuple of (tokenized_content, list_of_tokens)
        """
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="ignore")

        tokens = []

        for rule in self.rules:
            # Only tokenize if rule classification meets threshold
            if self._is_higher_privacy(classification_threshold, rule.classification) or classification_threshold == rule.classification:
                pattern = re.compile(rule.pattern, re.IGNORECASE)
                
                def replace_with_token(match):
                    matched_text = match.group(0)
                    token = self._generate_token(matched_text, rule.pii_type, rule.classification)
                    tokens.append(token)
                    return token.token
                
                content = pattern.sub(replace_with_token, content)

        return content, tokens

    def detokenize_content(self, content: str) -> str:
        """Restore original content from tokenized content.

        Args:
            content: Content with privacy tokens

        Returns:
            Original content with tokens replaced by original values
        """
        # Find all tokens in the content
        token_pattern = re.compile(r"(\[TOKEN_\w+_\d+\])")
        parts = token_pattern.split(content)
        
        result = []
        for part in parts:
            if part.startswith("[TOKEN_") and part.endswith("]"):
                # Look up the original value
                original_value = self._lookup_original_value(part)
                if original_value:
                    result.append(original_value)
                else:
                    result.append(part)  # Keep token if not found
            else:
                result.append(part)
        
        return "".join(result)

    def validate_for_publication(self, content: Union[str, bytes]) -> tuple[bool, List[str]]:
        """Validate content for publication safety.

        Args:
            content: Content to validate

        Returns:
            Tuple of (is_safe, list_of_issues_found)
        """
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="ignore")

        issues = []

        # Check for restricted content
        for rule in self.rules:
            if rule.classification == PrivacyClassification.RESTRICTED:
                pattern = re.compile(rule.pattern, re.IGNORECASE)
                matches = pattern.findall(content)
                if matches:
                    issues.append(f"Found {rule.pii_type.value} in restricted content: {matches[:5]}...")

        # Check for third-party private content that might need consent
        for rule in self.rules:
            if rule.classification == PrivacyClassification.THIRD_PARTY_PRIVATE:
                pattern = re.compile(rule.pattern, re.IGNORECASE)
                matches = pattern.findall(content)
                if matches:
                    issues.append(f"Found {rule.pii_type.value} that may require consent: {matches[:5]}...")

        # Check for sensitive content
        for rule in self.rules:
            if rule.classification == PrivacyClassification.SENSITIVE:
                pattern = re.compile(rule.pattern, re.IGNORECASE)
                matches = pattern.findall(content)
                if matches:
                    issues.append(f"Found {rule.pii_type.value} that may need special handling: {matches[:5]}...")

        return len(issues) == 0, issues

    def _generate_token(self, original_value: str, pii_type: PiiType, classification: PrivacyClassification) -> PrivacyToken:
        """Generate a privacy token for sensitive information.

        Args:
            original_value: The original sensitive value
            pii_type: Type of PII
            classification: Privacy classification

        Returns:
            PrivacyToken object
        """
        self.token_counter += 1
        token = f"[TOKEN_{pii_type.value.upper()}_{self.token_counter}]"
        
        privacy_token = PrivacyToken(
            original_value=original_value,
            token=token,
            pii_type=pii_type,
            classification=classification,
        )
        
        self.token_store[token] = privacy_token
        return privacy_token

    def _lookup_original_value(self, token: str) -> Optional[str]:
        """Lookup the original value for a token.

        Args:
            token: The privacy token

        Returns:
            Original value or None if not found
        """
        privacy_token = self.token_store.get(token)
        return privacy_token.original_value if privacy_token else None

    def _is_higher_privacy(self, classification1: PrivacyClassification, classification2: PrivacyClassification) -> bool:
        """Check if classification2 is higher privacy level than classification1.

        Order: PUBLIC < PRIVATE < SENSITIVE < THIRD_PARTY_PRIVATE < RESTRICTED

        Args:
            classification1: First classification
            classification2: Second classification

        Returns:
            True if classification2 is higher privacy level
        """
        privacy_order = {
            PrivacyClassification.PUBLIC: 0,
            PrivacyClassification.PRIVATE: 1,
            PrivacyClassification.SENSITIVE: 2,
            PrivacyClassification.THIRD_PARTY_PRIVATE: 3,
            PrivacyClassification.RESTRICTED: 4,
        }
        
        return privacy_order.get(classification2, 0) > privacy_order.get(classification1, 0)

    def analyze_source_path(self, source_path: str) -> PrivacyClassification:
        """Analyze a source path for privacy implications.

        Args:
            source_path: Path to analyze

        Returns:
            Privacy classification based on path
        """
        path_lower = source_path.lower()
        
        # Check for credential-related paths
        credential_patterns = [
            "password", "secret", "token", "key", "credential", "config", "auth", "ssh", "gpg"
        ]
        
        for pattern in credential_patterns:
            if pattern in path_lower:
                return PrivacyClassification.RESTRICTED
        
        # Check for personal information paths
        personal_patterns = [
            "contact", "address", "medical", "health", "finance", "bank", "tax", "ssn"
        ]
        
        for pattern in personal_patterns:
            if pattern in path_lower:
                return PrivacyClassification.SENSITIVE
        
        # Default to PRIVATE for most paths
        return PrivacyClassification.PRIVATE

    def get_privacy_report(self) -> Dict[str, Any]:
        """Generate a privacy report with statistics.

        Returns:
            Dictionary with privacy statistics
        """
        classifications = {}
        pii_types = {}
        
        for token in self.token_store.values():
            # Count classifications
            cls = token.classification.value
            classifications[cls] = classifications.get(cls, 0) + 1
            
            # Count PII types
            pii = token.pii_type.value
            pii_types[pii] = pii_types.get(pii, 0) + 1
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "total_tokens": len(self.token_store),
            "classifications": classifications,
            "pii_types": pii_types,
            "token_counter": self.token_counter,
        }


# Global instance for use throughout the application
privacy_engine = PrivacyEngine()
