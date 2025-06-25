# utils/validation.py
"""
GreenRec Validation Utilities
============================

Validációs funkciók a GreenRec alkalmazáshoz.
Tartalmazza az input validációt, adatstruktúra ellenőrzést, biztonsági validációkat és API payload validációt.
"""

import re
import json
import uuid
from typing import Any, Dict, List, Optional, Union, Tuple, Set
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from dataclasses import dataclass
from enum import Enum
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# =====================================
# Validation Result Classes
# =====================================

class ValidationLevel(Enum):
    """Validációs szintek"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

@dataclass
class ValidationResult:
    """Validációs eredmény objektum"""
    is_valid: bool
    level: ValidationLevel
    message: str
    field: Optional[str] = None
    value: Any = None
    suggestion: Optional[str] = None
    error_code: Optional[str] = None

@dataclass
class ValidationReport:
    """Komplex validációs jelentés"""
    overall_valid: bool
    total_checks: int
    passed_checks: int
    failed_checks: int
    results: List[ValidationResult]
    summary: Dict[str, int]
    
    def get_errors(self) -> List[ValidationResult]:
        """Csak a hibák lekérdezése"""
        return [r for r in self.results if r.level in [ValidationLevel.ERROR, ValidationLevel.CRITICAL]]
    
    def get_warnings(self) -> List[ValidationResult]:
        """Csak a figyelmeztetések lekérdezése"""
        return [r for r in self.results if r.level == ValidationLevel.WARNING]
    
    def to_dict(self) -> Dict[str, Any]:
        """Dictionary konverzió"""
        return {
            'overall_valid': self.overall_valid,
            'total_checks': self.total_checks,
            'passed_checks': self.passed_checks,
            'failed_checks': self.failed_checks,
            'summary': self.summary,
            'errors': [{'field': r.field, 'message': r.message, 'code': r.error_code} 
                      for r in self.get_errors()],
            'warnings': [{'field': r.field, 'message': r.message} 
                        for r in self.get_warnings()]
        }

# =====================================
# Basic Input Validation
# =====================================

class InputValidator:
    """Alapvető input validációs osztály"""
    
    @staticmethod
    def validate_rating(rating: Any) -> ValidationResult:
        """
        Értékelés validálása (1-5 skála)
        
        Args:
            rating: Validálandó értékelés
            
        Returns:
            ValidationResult objektum
        """
        try:
            # Type check
            if rating is None:
                return ValidationResult(
                    is_valid=False,
                    level=ValidationLevel.ERROR,
                    message="Rating cannot be None",
                    field="rating",
                    value=rating,
                    error_code="RATING_NULL"
                )
            
            # Convert to int
            rating_int = int(rating)
            
            # Range check
            if not (1 <= rating_int <= 5):
                return ValidationResult(
                    is_valid=False,
                    level=ValidationLevel.ERROR,
                    message=f"Rating must be between 1 and 5, got {rating_int}",
                    field="rating",
                    value=rating,
                    suggestion="Use a rating between 1 (worst) and 5 (best)",
                    error_code="RATING_OUT_OF_RANGE"
                )
            
            return ValidationResult(
                is_valid=True,
                level=ValidationLevel.INFO,
                message="Rating is valid",
                field="rating",
                value=rating_int
            )
            
        except (ValueError, TypeError):
            return ValidationResult(
                is_valid=False,
                level=ValidationLevel.ERROR,
                message=f"Rating must be a number, got {type(rating).__name__}",
                field="rating",
                value=rating,
                suggestion="Provide a number between 1 and 5",
                error_code="RATING_INVALID_TYPE"
            )
    
    @staticmethod
    def validate_recipe_id(recipe_id: Any) -> ValidationResult:
        """
        Recept ID validálása
        
        Args:
            recipe_id: Validálandó recept ID
            
        Returns:
            ValidationResult objektum
        """
        if recipe_id is None:
            return ValidationResult(
                is_valid=False,
                level=ValidationLevel.ERROR,
                message="Recipe ID cannot be None",
                field="recipe_id",
                value=recipe_id,
                error_code="RECIPE_ID_NULL"
            )
        
        # Convert to string
        recipe_id_str = str(recipe_id).strip()
        
        if not recipe_id_str:
            return ValidationResult(
                is_valid=False,
                level=ValidationLevel.ERROR,
                message="Recipe ID cannot be empty",
                field="recipe_id",
                value=recipe_id,
                error_code="RECIPE_ID_EMPTY"
            )
        
        # Length check
        if len(recipe_id_str) > 100:
            return ValidationResult(
                is_valid=False,
                level=ValidationLevel.ERROR,
                message=f"Recipe ID too long: {len(recipe_id_str)} characters (max 100)",
                field="recipe_id",
                value=recipe_id,
                error_code="RECIPE_ID_TOO_LONG"
            )
        
        # Character validation (alphanumeric + underscore + hyphen)
        if not re.match(r'^[a-zA-Z0-9_-]+$', recipe_id_str):
            return ValidationResult(
                is_valid=False,
                level=ValidationLevel.ERROR,
                message="Recipe ID contains invalid characters (only letters, numbers, underscore, hyphen allowed)",
                field="recipe_id",
                value=recipe_id,
                suggestion="Use only letters, numbers, underscore (_) and hyphen (-)",
                error_code="RECIPE_ID_INVALID_CHARS"
            )
        
        return ValidationResult(
            is_valid=True,
            level=ValidationLevel.INFO,
            message="Recipe ID is valid",
            field="recipe_id",
            value=recipe_id_str
        )
    
    @staticmethod
    def validate_search_query(query: Any, min_length: int = 1, max_length: int = 200) -> ValidationResult:
        """
        Keresési lekérdezés validálása
        
        Args:
            query: Keresési query
            min_length: Minimum hossz
            max_length: Maximum hossz
            
        Returns:
            ValidationResult objektum
        """
        if query is None:
            return ValidationResult(
                is_valid=False,
                level=ValidationLevel.ERROR,
                message="Search query cannot be None",
                field="query",
                value=query,
                error_code="QUERY_NULL"
            )
        
        # Convert to string and clean
        query_str = str(query).strip()
        
        if len(query_str) < min_length:
            return ValidationResult(
                is_valid=False,
                level=ValidationLevel.ERROR,
                message=f"Search query too short: {len(query_str)} characters (min {min_length})",
                field="query",
                value=query,
                suggestion=f"Enter at least {min_length} character(s)",
                error_code="QUERY_TOO_SHORT"
            )
        
        if len(query_str) > max_length:
            return ValidationResult(
                is_valid=False,
                level=ValidationLevel.ERROR,
                message=f"Search query too long: {len(query_str)} characters (max {max_length})",
                field="query",
                value=query,
                suggestion=f"Keep query under {max_length} characters",
                error_code="QUERY_TOO_LONG"
            )
        
        # Check for potentially malicious content
        suspicious_patterns = [
            r'<script',
            r'javascript:',
            r'eval\(',
            r'document\.cookie',
            r'window\.location'
        ]
        
        for pattern in suspicious_patterns:
            if re.search(pattern, query_str, re.IGNORECASE):
                return ValidationResult(
                    is_valid=False,
                    level=ValidationLevel.CRITICAL,
                    message="Search query contains potentially malicious content",
                    field="query",
                    value=query,
                    error_code="QUERY_SUSPICIOUS_CONTENT"
                )
        
        return ValidationResult(
            is_valid=True,
            level=ValidationLevel.INFO,
            message="Search query is valid",
            field="query",
            value=query_str
        )
    
    @staticmethod
    def validate_user_group(user_group: Any) -> ValidationResult:
        """
        Felhasználói csoport validálása
        
        Args:
            user_group: Felhasználói csoport
            
        Returns:
            ValidationResult objektum
        """
        valid_groups = {'A', 'B', 'C'}
        
        if user_group is None:
            return ValidationResult(
                is_valid=False,
                level=ValidationLevel.ERROR,
                message="User group cannot be None",
                field="user_group",
                value=user_group,
                error_code="USER_GROUP_NULL"
            )
        
        user_group_str = str(user_group).strip().upper()
        
        if user_group_str not in valid_groups:
            return ValidationResult(
                is_valid=False,
                level=ValidationLevel.ERROR,
                message=f"Invalid user group: {user_group_str} (must be A, B, or C)",
                field="user_group",
                value=user_group,
                suggestion="Use 'A', 'B', or 'C'",
                error_code="USER_GROUP_INVALID"
            )
        
        return ValidationResult(
            is_valid=True,
            level=ValidationLevel.INFO,
            message="User group is valid",
            field="user_group",
            value=user_group_str
        )
    
    @staticmethod
    def validate_learning_round(learning_round: Any, min_round: int = 1, max_round: int = 10) -> ValidationResult:
        """
        Tanulási kör validálása
        
        Args:
            learning_round: Tanulási kör száma
            min_round: Minimum kör
            max_round: Maximum kör
            
        Returns:
            ValidationResult objektum
        """
        try:
            if learning_round is None:
                return ValidationResult(
                    is_valid=False,
                    level=ValidationLevel.ERROR,
                    message="Learning round cannot be None",
                    field="learning_round",
                    value=learning_round,
                    error_code="LEARNING_ROUND_NULL"
                )
            
            round_int = int(learning_round)
            
            if not (min_round <= round_int <= max_round):
                return ValidationResult(
                    is_valid=False,
                    level=ValidationLevel.ERROR,
                    message=f"Learning round must be between {min_round} and {max_round}, got {round_int}",
                    field="learning_round",
                    value=learning_round,
                    suggestion=f"Use a round number between {min_round} and {max_round}",
                    error_code="LEARNING_ROUND_OUT_OF_RANGE"
                )
            
            return ValidationResult(
                is_valid=True,
                level=ValidationLevel.INFO,
                message="Learning round is valid",
                field="learning_round",
                value=round_int
            )
            
        except (ValueError, TypeError):
            return ValidationResult(
                is_valid=False,
                level=ValidationLevel.ERROR,
                message=f"Learning round must be a number, got {type(learning_round).__name__}",
                field="learning_round",
                value=learning_round,
                suggestion=f"Provide a number between {min_round} and {max_round}",
                error_code="LEARNING_ROUND_INVALID_TYPE"
            )

# =====================================
# API Payload Validation
# =====================================

class APIValidator:
    """API payload validációs osztály"""
    
    @staticmethod
    def validate_rating_request(payload: Dict[str, Any]) -> ValidationReport:
        """
        Rating API kérés validálása
        
        Args:
            payload: API payload
            
        Returns:
            ValidationReport objektum
        """
        results = []
        
        # Required fields check
        required_fields = ['recipe_id', 'rating']
        for field in required_fields:
            if field not in payload:
                results.append(ValidationResult(
                    is_valid=False,
                    level=ValidationLevel.ERROR,
                    message=f"Missing required field: {field}",
                    field=field,
                    error_code=f"MISSING_{field.upper()}"
                ))
        
        # Validate individual fields
        if 'recipe_id' in payload:
            recipe_id_result = InputValidator.validate_recipe_id(payload['recipe_id'])
            results.append(recipe_id_result)
        
        if 'rating' in payload:
            rating_result = InputValidator.validate_rating(payload['rating'])
            results.append(rating_result)
        
        # Optional timestamp validation
        if 'timestamp' in payload:
            timestamp_result = APIValidator._validate_timestamp(payload['timestamp'])
            results.append(timestamp_result)
        
        # Check for unexpected fields
        expected_fields = {'recipe_id', 'rating', 'timestamp', 'user_id', 'session_id'}
        unexpected_fields = set(payload.keys()) - expected_fields
        
        if unexpected_fields:
            results.append(ValidationResult(
                is_valid=False,
                level=ValidationLevel.WARNING,
                message=f"Unexpected fields in payload: {list(unexpected_fields)}",
                field="payload",
                value=unexpected_fields,
                error_code="UNEXPECTED_FIELDS"
            ))
        
        return APIValidator._create_validation_report(results)
    
    @staticmethod
    def validate_search_request(payload: Dict[str, Any]) -> ValidationReport:
        """
        Search API kérés validálása
        
        Args:
            payload: API payload
            
        Returns:
            ValidationReport objektum
        """
        results = []
        
        # Query validation
        if 'query' not in payload and 'q' not in payload:
            results.append(ValidationResult(
                is_valid=False,
                level=ValidationLevel.ERROR,
                message="Missing search query (provide 'query' or 'q')",
                field="query",
                error_code="MISSING_QUERY"
            ))
        else:
            query = payload.get('query') or payload.get('q')
            query_result = InputValidator.validate_search_query(query)
            results.append(query_result)
        
        # Optional parameters validation
        if 'limit' in payload:
            limit_result = APIValidator._validate_limit(payload['limit'])
            results.append(limit_result)
        
        if 'offset' in payload:
            offset_result = APIValidator._validate_offset(payload['offset'])
            results.append(offset_result)
        
        if 'filters' in payload:
            filters_result = APIValidator._validate_search_filters(payload['filters'])
            results.append(filters_result)
        
        return APIValidator._create_validation_report(results)
    
    @staticmethod
    def validate_recommendation_request(payload: Dict[str, Any]) -> ValidationReport:
        """
        Recommendation API kérés validálása
        
        Args:
            payload: API payload
            
        Returns:
            ValidationReport objektum
        """
        results = []
        
        # User identification
        if 'user_id' not in payload and 'session_id' not in payload:
            results.append(ValidationResult(
                is_valid=False,
                level=ValidationLevel.ERROR,
                message="Missing user identification (provide 'user_id' or 'session_id')",
                field="user_identification",
                error_code="MISSING_USER_ID"
            ))
        
        # Optional parameters
        if 'count' in payload:
            count_result = APIValidator._validate_recommendation_count(payload['count'])
            results.append(count_result)
        
        if 'user_group' in payload:
            group_result = InputValidator.validate_user_group(payload['user_group'])
            results.append(group_result)
        
        if 'learning_round' in payload:
            round_result = InputValidator.validate_learning_round(payload['learning_round'])
            results.append(round_result)
        
        # Preferences validation
        if 'preferences' in payload:
            prefs_result = APIValidator._validate_user_preferences(payload['preferences'])
            results.append(prefs_result)
        
        return APIValidator._create_validation_report(results)
    
    @staticmethod
    def _validate_timestamp(timestamp: Any) -> ValidationResult:
        """Timestamp validálása"""
        if timestamp is None:
            return ValidationResult(
                is_valid=True,
                level=ValidationLevel.INFO,
                message="Timestamp is optional",
                field="timestamp"
            )
        
        try:
            # Try to parse as ISO format
            if isinstance(timestamp, str):
                parsed_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            else:
                parsed_time = datetime.fromtimestamp(float(timestamp))
            
            # Check if timestamp is reasonable (not too old, not in future)
            now = datetime.now()
            one_day_ago = now - timedelta(days=1)
            one_hour_future = now + timedelta(hours=1)
            
            if parsed_time < one_day_ago:
                return ValidationResult(
                    is_valid=False,
                    level=ValidationLevel.WARNING,
                    message="Timestamp is more than 24 hours old",
                    field="timestamp",
                    value=timestamp,
                    error_code="TIMESTAMP_TOO_OLD"
                )
            
            if parsed_time > one_hour_future:
                return ValidationResult(
                    is_valid=False,
                    level=ValidationLevel.ERROR,
                    message="Timestamp is in the future",
                    field="timestamp",
                    value=timestamp,
                    error_code="TIMESTAMP_FUTURE"
                )
            
            return ValidationResult(
                is_valid=True,
                level=ValidationLevel.INFO,
                message="Timestamp is valid",
                field="timestamp",
                value=parsed_time
            )
            
        except (ValueError, TypeError, OSError):
            return ValidationResult(
                is_valid=False,
                level=ValidationLevel.ERROR,
                message="Invalid timestamp format",
                field="timestamp",
                value=timestamp,
                suggestion="Use ISO format (YYYY-MM-DDTHH:MM:SS) or Unix timestamp",
                error_code="TIMESTAMP_INVALID_FORMAT"
            )
    
    @staticmethod
    def _validate_limit(limit: Any) -> ValidationResult:
        """Limit parameter validálása"""
        try:
            limit_int = int(limit)
            
            if not (1 <= limit_int <= 100):
                return ValidationResult(
                    is_valid=False,
                    level=ValidationLevel.ERROR,
                    message=f"Limit must be between 1 and 100, got {limit_int}",
                    field="limit",
                    value=limit,
                    error_code="LIMIT_OUT_OF_RANGE"
                )
            
            return ValidationResult(
                is_valid=True,
                level=ValidationLevel.INFO,
                message="Limit is valid",
                field="limit",
                value=limit_int
            )
            
        except (ValueError, TypeError):
            return ValidationResult(
                is_valid=False,
                level=ValidationLevel.ERROR,
                message="Limit must be a number",
                field="limit",
                value=limit,
                error_code="LIMIT_INVALID_TYPE"
            )
    
    @staticmethod
    def _validate_offset(offset: Any) -> ValidationResult:
        """Offset parameter validálása"""
        try:
            offset_int = int(offset)
            
            if offset_int < 0:
                return ValidationResult(
                    is_valid=False,
                    level=ValidationLevel.ERROR,
                    message=f"Offset cannot be negative, got {offset_int}",
                    field="offset",
                    value=offset,
                    error_code="OFFSET_NEGATIVE"
                )
            
            if offset_int > 10000:
                return ValidationResult(
                    is_valid=False,
                    level=ValidationLevel.WARNING,
                    message=f"Very high offset: {offset_int} (performance impact)",
                    field="offset",
                    value=offset,
                    error_code="OFFSET_HIGH"
                )
            
            return ValidationResult(
                is_valid=True,
                level=ValidationLevel.INFO,
                message="Offset is valid",
                field="offset",
                value=offset_int
            )
            
        except (ValueError, TypeError):
            return ValidationResult(
                is_valid=False,
                level=ValidationLevel.ERROR,
                message="Offset must be a number",
                field="offset",
                value=offset,
                error_code="OFFSET_INVALID_TYPE"
            )
    
    @staticmethod
    def _validate_recommendation_count(count: Any) -> ValidationResult:
        """Recommendation count validálása"""
        try:
            count_int = int(count)
            
            if not (1 <= count_int <= 50):
                return ValidationResult(
                    is_valid=False,
                    level=ValidationLevel.ERROR,
                    message=f"Recommendation count must be between 1 and 50, got {count_int}",
                    field="count",
                    value=count,
                    error_code="COUNT_OUT_OF_RANGE"
                )
            
            return ValidationResult(
                is_valid=True,
                level=ValidationLevel.INFO,
                message="Recommendation count is valid",
                field="count",
                value=count_int
            )
            
        except (ValueError, TypeError):
            return ValidationResult(
                is_valid=False,
                level=ValidationLevel.ERROR,
                message="Recommendation count must be a number",
                field="count",
                value=count,
                error_code="COUNT_INVALID_TYPE"
            )
    
    @staticmethod
    def _validate_search_filters(filters: Any) -> ValidationResult:
        """Search filters validálása"""
        if not isinstance(filters, dict):
            return ValidationResult(
                is_valid=False,
                level=ValidationLevel.ERROR,
                message="Filters must be a dictionary",
                field="filters",
                value=filters,
                error_code="FILTERS_INVALID_TYPE"
            )
        
        valid_filter_keys = {
            'categories', 'ingredients', 'min_sustainability', 'max_sustainability',
            'min_health', 'max_health', 'vegetarian', 'vegan', 'gluten_free'
        }
        
        invalid_keys = set(filters.keys()) - valid_filter_keys
        
        if invalid_keys:
            return ValidationResult(
                is_valid=False,
                level=ValidationLevel.WARNING,
                message=f"Unknown filter keys: {list(invalid_keys)}",
                field="filters",
                value=filters,
                suggestion=f"Valid keys: {list(valid_filter_keys)}",
                error_code="FILTERS_UNKNOWN_KEYS"
            )
        
        # Validate specific filter values
        for key, value in filters.items():
            if key in ['min_sustainability', 'max_sustainability', 'min_health', 'max_health']:
                try:
                    float_val = float(value)
                    if not (0 <= float_val <= 100):
                        return ValidationResult(
                            is_valid=False,
                            level=ValidationLevel.ERROR,
                            message=f"Filter {key} must be between 0 and 100, got {float_val}",
                            field=f"filters.{key}",
                            value=value,
                            error_code="FILTER_VALUE_OUT_OF_RANGE"
                        )
                except (ValueError, TypeError):
                    return ValidationResult(
                        is_valid=False,
                        level=ValidationLevel.ERROR,
                        message=f"Filter {key} must be a number",
                        field=f"filters.{key}",
                        value=value,
                        error_code="FILTER_VALUE_INVALID_TYPE"
                    )
        
        return ValidationResult(
            is_valid=True,
            level=ValidationLevel.INFO,
            message="Search filters are valid",
            field="filters",
            value=filters
        )
    
    @staticmethod
    def _validate_user_preferences(preferences: Any) -> ValidationResult:
        """User preferences validálása"""
        if not isinstance(preferences, dict):
            return ValidationResult(
                is_valid=False,
                level=ValidationLevel.ERROR,
                message="Preferences must be a dictionary",
                field="preferences",
                value=preferences,
                error_code="PREFERENCES_INVALID_TYPE"
            )
        
        valid_pref_keys = {
            'preferred_categories', 'preferred_ingredients', 'dietary_restrictions',
            'sustainability_importance', 'health_importance', 'novelty_preference'
        }
        
        # Check for known preference keys
        unknown_keys = set(preferences.keys()) - valid_pref_keys
        if unknown_keys:
            return ValidationResult(
                is_valid=False,
                level=ValidationLevel.WARNING,
                message=f"Unknown preference keys: {list(unknown_keys)}",
                field="preferences",
                value=preferences,
                error_code="PREFERENCES_UNKNOWN_KEYS"
            )
        
        # Validate specific preference values
        for key, value in preferences.items():
            if key in ['sustainability_importance', 'health_importance', 'novelty_preference']:
                try:
                    float_val = float(value)
                    if not (0 <= float_val <= 1):
                        return ValidationResult(
                            is_valid=False,
                            level=ValidationLevel.ERROR,
                            message=f"Preference {key} must be between 0 and 1, got {float_val}",
                            field=f"preferences.{key}",
                            value=value,
                            error_code="PREFERENCE_VALUE_OUT_OF_RANGE"
                        )
                except (ValueError, TypeError):
                    return ValidationResult(
                        is_valid=False,
                        level=ValidationLevel.ERROR,
                        message=f"Preference {key} must be a number",
                        field=f"preferences.{key}",
                        value=value,
                        error_code="PREFERENCE_VALUE_INVALID_TYPE"
                    )
        
        return ValidationResult(
            is_valid=True,
            level=ValidationLevel.INFO,
            message="User preferences are valid",
            field="preferences",
            value=preferences
        )
    
    @staticmethod
    def _create_validation_report(results: List[ValidationResult]) -> ValidationReport:
        """ValidationReport létrehozása eredmények listájából"""
        total_checks = len(results)
        failed_checks = len([r for r in results if not r.is_valid])
        passed_checks = total_checks - failed_checks
        
        # Overall validity (no errors or critical issues)
        overall_valid = not any(r.level in [ValidationLevel.ERROR, ValidationLevel.CRITICAL] 
                               for r in results if not r.is_valid)
        
        # Summary by level
        summary = {
            'info': len([r for r in results if r.level == ValidationLevel.INFO]),
            'warning': len([r for r in results if r.level == ValidationLevel.WARNING]),
            'error': len([r for r in results if r.level == ValidationLevel.ERROR]),
            'critical': len([r for r in results if r.level == ValidationLevel.CRITICAL])
        }
        
        return ValidationReport(
            overall_valid=overall_valid,
            total_checks=total_checks,
            passed_checks=passed_checks,
            failed_checks=failed_checks,
            results=results,
            summary=summary
        )

# =====================================
# Data Structure Validation
# =====================================

class DataStructureValidator:
    """Adatstruktúra validációs osztály"""
    
    @staticmethod
    def validate_recipe_data(recipe: Dict[str, Any]) -> ValidationReport:
        """
        Recept adatok validálása
        
        Args:
            recipe: Recept dictionary
            
        Returns:
            ValidationReport objektum
        """
        results = []
        
        # Required fields
        required_fields = ['id', 'name']
        for field in required_fields:
            if field not in recipe:
                results.append(ValidationResult(
                    is_valid=False,
                    level=ValidationLevel.ERROR,
                    message=f"Missing required field: {field}",
                    field=field,
                    error_code=f"MISSING_{field.upper()}"
                ))
            elif not recipe[field]:
                results.append(ValidationResult(
                    is_valid=False,
                    level=ValidationLevel.ERROR,
                    message=f"Field {field} cannot be empty",
                    field=field,
                    value=recipe[field],
                    error_code=f"{field.upper()}_EMPTY"
                ))
        
        # Validate ID
        if 'id' in recipe:
            id_result = InputValidator.validate_recipe_id(recipe['id'])
            results.append(id_result)
        
        # Validate name
        if 'name' in recipe:
            name_result = DataStructureValidator._validate_recipe_name(recipe['name'])
            results.append(name_result)
        
        # Validate optional numeric fields
        numeric_fields = ['ESI', 'HSI', 'PPI', 'composite_score']
        for field in numeric_fields:
            if field in recipe:
                numeric_result = DataStructureValidator._validate_numeric_score(
                    recipe[field], field
                )
                results.append(numeric_result)
        
        # Validate optional list fields
        list_fields = ['ingredients', 'categories']
        for field in list_fields:
            if field in recipe:
                list_result = DataStructureValidator._validate_list_field(
                    recipe[field], field
                )
                results.append(list_result)
        
        return APIValidator._create_validation_report(results)
    
    @staticmethod
    def validate_user_session_data(session_data: Dict[str, Any]) -> ValidationReport:
        """
        User session adatok validálása
        
        Args:
            session_data: Session dictionary
            
        Returns:
            ValidationReport objektum
        """
        results = []
        
        # Required session fields
        required_fields = ['user_id', 'user_group']
        for field in required_fields:
            if field not in session_data:
                results.append(ValidationResult(
                    is_valid=False,
                    level=ValidationLevel.ERROR,
                    message=f"Missing required session field: {field}",
                    field=field,
                    error_code=f"MISSING_SESSION_{field.upper()}"
                ))
        
        # Validate user_group
        if 'user_group' in session_data:
            group_result = InputValidator.validate_user_group(session_data['user_group'])
            results.append(group_result)
        
        # Validate learning_round
        if 'learning_round' in session_data:
            round_result = InputValidator.validate_learning_round(session_data['learning_round'])
            results.append(round_result)
        
        # Validate ratings dictionary
        if 'ratings' in session_data:
            ratings_result = DataStructureValidator._validate_ratings_dict(session_data['ratings'])
            results.append(ratings_result)
        
        # Validate timestamps
        timestamp_fields = ['created_at', 'last_activity']
        for field in timestamp_fields:
            if field in session_data:
                timestamp_result = APIValidator._validate_timestamp(session_data[field])
                results.append(timestamp_result)
        
        return APIValidator._create_validation_report(results)
    
    @staticmethod
    def validate_dataframe_structure(df: pd.DataFrame, 
                                   required_columns: List[str] = None) -> ValidationReport:
        """
        DataFrame struktúra validálása
        
        Args:
            df: Validálandó DataFrame
            required_columns: Kötelező oszlopok listája
            
        Returns:
            ValidationReport objektum
        """
        results = []
        
        if required_columns is None:
            required_columns = ['id', 'name']
        
        # Check if DataFrame is empty
        if df.empty:
            results.append(ValidationResult(
                is_valid=False,
                level=ValidationLevel.ERROR,
                message="DataFrame is empty",
                field="dataframe",
                error_code="DATAFRAME_EMPTY"
            ))
            return APIValidator._create_validation_report(results)
        
        # Check required columns
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            results.append(ValidationResult(
                is_valid=False,
                level=ValidationLevel.ERROR,
                message=f"Missing required columns: {missing_columns}",
                field="dataframe_columns",
                value=missing_columns,
                error_code="MISSING_COLUMNS"
            ))
        
        # Check for duplicate IDs
        if 'id' in df.columns:
            duplicate_ids = df['id'].duplicated().sum()
            if duplicate_ids > 0:
                results.append(ValidationResult(
                    is_valid=False,
                    level=ValidationLevel.ERROR,
                    message=f"Found {duplicate_ids} duplicate IDs",
                    field="id",
                    value=duplicate_ids,
                    error_code="DUPLICATE_IDS"
                ))
        
        # Check data types and null values
        for col in df.columns:
            null_count = df[col].isnull().sum()
            null_percentage = (null_count / len(df)) * 100
            
            if null_percentage > 50:
                results.append(ValidationResult(
                    is_valid=False,
                    level=ValidationLevel.WARNING,
                    message=f"Column {col} has {null_percentage:.1f}% null values",
                    field=col,
                    value=null_percentage,
                    error_code="HIGH_NULL_PERCENTAGE"
                ))
        
        # Validate numeric columns ranges
        numeric_columns = ['ESI', 'HSI', 'PPI', 'composite_score']
        for col in numeric_columns:
            if col in df.columns:
                try:
                    numeric_data = pd.to_numeric(df[col], errors='coerce')
                    
                    # Check for values outside expected range (0-100)
                    out_of_range = ((numeric_data < 0) | (numeric_data > 100)).sum()
                    if out_of_range > 0:
                        results.append(ValidationResult(
                            is_valid=False,
                            level=ValidationLevel.WARNING,
                            message=f"Column {col} has {out_of_range} values outside 0-100 range",
                            field=col,
                            value=out_of_range,
                            error_code="VALUES_OUT_OF_RANGE"
                        ))
                
                except Exception as e:
                    results.append(ValidationResult(
                        is_valid=False,
                        level=ValidationLevel.ERROR,
                        message=f"Column {col} validation failed: {str(e)}",
                        field=col,
                        error_code="COLUMN_VALIDATION_ERROR"
                    ))
        
        return APIValidator._create_validation_report(results)
    
    @staticmethod
    def _validate_recipe_name(name: Any) -> ValidationResult:
        """Recept név validálása"""
        if not name:
            return ValidationResult(
                is_valid=False,
                level=ValidationLevel.ERROR,
                message="Recipe name cannot be empty",
                field="name",
                value=name,
                error_code="NAME_EMPTY"
            )
        
        name_str = str(name).strip()
        
        if len(name_str) < 2:
            return ValidationResult(
                is_valid=False,
                level=ValidationLevel.ERROR,
                message=f"Recipe name too short: {len(name_str)} characters (min 2)",
                field="name",
                value=name,
                error_code="NAME_TOO_SHORT"
            )
        
        if len(name_str) > 200:
            return ValidationResult(
                is_valid=False,
                level=ValidationLevel.WARNING,
                message=f"Recipe name very long: {len(name_str)} characters",
                field="name",
                value=name,
                error_code="NAME_VERY_LONG"
            )
        
        return ValidationResult(
            is_valid=True,
            level=ValidationLevel.INFO,
            message="Recipe name is valid",
            field="name",
            value=name_str
        )
    
    @staticmethod
    def _validate_numeric_score(score: Any, field_name: str) -> ValidationResult:
        """Numerikus pontszám validálása"""
        try:
            if score is None:
                return ValidationResult(
                    is_valid=True,
                    level=ValidationLevel.INFO,
                    message=f"{field_name} is optional (None)",
                    field=field_name,
                    value=score
                )
            
            score_float = float(score)
            
            # Check for reasonable range (0-100 for most scores)
            if not (0 <= score_float <= 100):
                return ValidationResult(
                    is_valid=False,
                    level=ValidationLevel.WARNING,
                    message=f"{field_name} outside expected range 0-100: {score_float}",
                    field=field_name,
                    value=score,
                    error_code=f"{field_name.upper()}_OUT_OF_RANGE"
                )
            
            return ValidationResult(
                is_valid=True,
                level=ValidationLevel.INFO,
                message=f"{field_name} is valid",
                field=field_name,
                value=score_float
            )
            
        except (ValueError, TypeError):
            return ValidationResult(
                is_valid=False,
                level=ValidationLevel.ERROR,
                message=f"{field_name} must be a number, got {type(score).__name__}",
                field=field_name,
                value=score,
                error_code=f"{field_name.upper()}_INVALID_TYPE"
            )
    
    @staticmethod
    def _validate_list_field(list_data: Any, field_name: str) -> ValidationResult:
        """Lista mező validálása"""
        if list_data is None:
            return ValidationResult(
                is_valid=True,
                level=ValidationLevel.INFO,
                message=f"{field_name} is optional (None)",
                field=field_name,
                value=list_data
            )
        
        # Convert string to list if needed (comma-separated)
        if isinstance(list_data, str):
            list_items = [item.strip() for item in list_data.split(',')]
        elif isinstance(list_data, list):
            list_items = list_data
        else:
            return ValidationResult(
                is_valid=False,
                level=ValidationLevel.ERROR,
                message=f"{field_name} must be a list or comma-separated string",
                field=field_name,
                value=list_data,
                error_code=f"{field_name.upper()}_INVALID_TYPE"
            )
        
        # Check list length
        if len(list_items) > 50:
            return ValidationResult(
                is_valid=False,
                level=ValidationLevel.WARNING,
                message=f"{field_name} has many items: {len(list_items)} (performance impact)",
                field=field_name,
                value=list_data,
                error_code=f"{field_name.upper()}_TOO_MANY_ITEMS"
            )
        
        # Check individual items
        empty_items = [item for item in list_items if not str(item).strip()]
        if empty_items:
            return ValidationResult(
                is_valid=False,
                level=ValidationLevel.WARNING,
                message=f"{field_name} contains {len(empty_items)} empty items",
                field=field_name,
                value=list_data,
                error_code=f"{field_name.upper()}_EMPTY_ITEMS"
            )
        
        return ValidationResult(
            is_valid=True,
            level=ValidationLevel.INFO,
            message=f"{field_name} is valid",
            field=field_name,
            value=list_items
        )
    
    @staticmethod
    def _validate_ratings_dict(ratings: Any) -> ValidationResult:
        """Ratings dictionary validálása"""
        if not isinstance(ratings, dict):
            return ValidationResult(
                is_valid=False,
                level=ValidationLevel.ERROR,
                message="Ratings must be a dictionary",
                field="ratings",
                value=ratings,
                error_code="RATINGS_INVALID_TYPE"
            )
        
        # Check each rating
        for recipe_id, rating in ratings.items():
            # Validate recipe_id
            id_result = InputValidator.validate_recipe_id(recipe_id)
            if not id_result.is_valid:
                return ValidationResult(
                    is_valid=False,
                    level=ValidationLevel.ERROR,
                    message=f"Invalid recipe_id in ratings: {recipe_id}",
                    field="ratings",
                    value=ratings,
                    error_code="RATINGS_INVALID_RECIPE_ID"
                )
            
            # Validate rating value
            rating_result = InputValidator.validate_rating(rating)
            if not rating_result.is_valid:
                return ValidationResult(
                    is_valid=False,
                    level=ValidationLevel.ERROR,
                    message=f"Invalid rating value for {recipe_id}: {rating}",
                    field="ratings",
                    value=ratings,
                    error_code="RATINGS_INVALID_RATING_VALUE"
                )
        
        return ValidationResult(
            is_valid=True,
            level=ValidationLevel.INFO,
            message="Ratings dictionary is valid",
            field="ratings",
            value=ratings
        )

# =====================================
# Security Validation
# =====================================

class SecurityValidator:
    """Biztonsági validációs osztály"""
    
    @staticmethod
    def validate_input_against_xss(input_data: str) -> ValidationResult:
        """
        XSS védelem validálása
        
        Args:
            input_data: Validálandó input string
            
        Returns:
            ValidationResult objektum
        """
        if not isinstance(input_data, str):
            return ValidationResult(
                is_valid=True,
                level=ValidationLevel.INFO,
                message="Input is not string, XSS check skipped",
                field="xss_check"
            )
        
        # Suspicious patterns that might indicate XSS attempts
        xss_patterns = [
            r'<script[^>]*>',
            r'</script>',
            r'javascript:',
            r'vbscript:',
            r'onload\s*=',
            r'onerror\s*=',
            r'onclick\s*=',
            r'onmouseover\s*=',
            r'eval\s*\(',
            r'document\.cookie',
            r'document\.write',
            r'window\.location',
            r'innerHTML\s*=',
            r'<iframe[^>]*>',
            r'<object[^>]*>',
            r'<embed[^>]*>'
        ]
        
        for pattern in xss_patterns:
            if re.search(pattern, input_data, re.IGNORECASE):
                return ValidationResult(
                    is_valid=False,
                    level=ValidationLevel.CRITICAL,
                    message="Input contains potentially malicious content (XSS)",
                    field="security",
                    value=input_data,
                    error_code="XSS_DETECTED"
                )
        
        return ValidationResult(
            is_valid=True,
            level=ValidationLevel.INFO,
            message="Input passed XSS validation",
            field="security"
        )
    
    @staticmethod
    def validate_input_against_sql_injection(input_data: str) -> ValidationResult:
        """
        SQL injection védelem validálása
        
        Args:
            input_data: Validálandó input string
            
        Returns:
            ValidationResult objektum
        """
        if not isinstance(input_data, str):
            return ValidationResult(
                is_valid=True,
                level=ValidationLevel.INFO,
                message="Input is not string, SQL injection check skipped",
                field="sql_injection_check"
            )
        
        # SQL injection patterns
        sql_patterns = [
            r'(\b(union|select|insert|update|delete|drop|create|alter|exec|execute)\b)',
            r'(--|\/\*|\*\/)',
            r'(\bor\b.*=.*=)',
            r'(\band\b.*=.*=)',
            r'(\'.*or.*\'.*=.*\')',
            r'(\".*or.*\".*=.*\")',
            r'(\bxp_cmdshell\b)',
            r'(\bsp_executesql\b)'
        ]
        
        for pattern in sql_patterns:
            if re.search(pattern, input_data, re.IGNORECASE):
                return ValidationResult(
                    is_valid=False,
                    level=ValidationLevel.CRITICAL,
                    message="Input contains potentially malicious content (SQL injection)",
                    field="security",
                    value=input_data,
                    error_code="SQL_INJECTION_DETECTED"
                )
        
        return ValidationResult(
            is_valid=True,
            level=ValidationLevel.INFO,
            message="Input passed SQL injection validation",
            field="security"
        )
    
    @staticmethod
    def validate_file_upload_security(filename: str, file_content: bytes = None) -> ValidationReport:
        """
        Fájl feltöltés biztonsági validálása
        
        Args:
            filename: Fájl neve
            file_content: Fájl tartalma (opcionális)
            
        Returns:
            ValidationReport objektum
        """
        results = []
        
        # Filename validation
        if not filename:
            results.append(ValidationResult(
                is_valid=False,
                level=ValidationLevel.ERROR,
                message="Filename cannot be empty",
                field="filename",
                error_code="FILENAME_EMPTY"
            ))
        else:
            # Check for directory traversal
            if '..' in filename or '/' in filename or '\\' in filename:
                results.append(ValidationResult(
                    is_valid=False,
                    level=ValidationLevel.CRITICAL,
                    message="Filename contains directory traversal characters",
                    field="filename",
                    value=filename,
                    error_code="DIRECTORY_TRAVERSAL"
                ))
            
            # Check for dangerous extensions
            dangerous_extensions = {
                '.exe', '.bat', '.cmd', '.com', '.pif', '.scr', '.vbs', '.js',
                '.jar', '.php', '.asp', '.jsp', '.py', '.pl', '.sh'
            }
            
            file_ext = Path(filename).suffix.lower()
            if file_ext in dangerous_extensions:
                results.append(ValidationResult(
                    is_valid=False,
                    level=ValidationLevel.CRITICAL,
                    message=f"Dangerous file extension: {file_ext}",
                    field="filename",
                    value=filename,
                    error_code="DANGEROUS_EXTENSION"
                ))
            
            # Check allowed extensions for our use case
            allowed_extensions = {'.json', '.csv', '.txt', '.jpg', '.jpeg', '.png', '.gif'}
            if file_ext not in allowed_extensions:
                results.append(ValidationResult(
                    is_valid=False,
                    level=ValidationLevel.WARNING,
                    message=f"File extension not in allowed list: {file_ext}",
                    field="filename",
                    value=filename,
                    suggestion=f"Allowed extensions: {list(allowed_extensions)}",
                    error_code="EXTENSION_NOT_ALLOWED"
                ))
        
        # File content validation
        if file_content is not None:
            # Check file size (max 10MB)
            max_size = 10 * 1024 * 1024  # 10MB
            if len(file_content) > max_size:
                results.append(ValidationResult(
                    is_valid=False,
                    level=ValidationLevel.ERROR,
                    message=f"File too large: {len(file_content)} bytes (max {max_size})",
                    field="file_content",
                    error_code="FILE_TOO_LARGE"
                ))
            
            # Check for executable signatures
            executable_signatures = [
                b'MZ',  # Windows executable
                b'\x7fELF',  # Linux executable
                b'\xca\xfe\xba\xbe',  # Java class file
                b'PK',  # ZIP/JAR file
            ]
            
            for sig in executable_signatures:
                if file_content.startswith(sig):
                    results.append(ValidationResult(
                        is_valid=False,
                        level=ValidationLevel.CRITICAL,
                        message="File appears to be executable",
                        field="file_content",
                        error_code="EXECUTABLE_FILE_DETECTED"
                    ))
                    break
        
        return APIValidator._create_validation_report(results)

# =====================================
# Comprehensive Validation Functions
# =====================================

def validate_complete_recipe_submission(recipe_data: Dict[str, Any]) -> ValidationReport:
    """
    Teljes recept beküldés validálása
    
    Args:
        recipe_data: Recept adatok
        
    Returns:
        ValidationReport objektum
    """
    all_results = []
    
    # Basic structure validation
    structure_report = DataStructureValidator.validate_recipe_data(recipe_data)
    all_results.extend(structure_report.results)
    
    # Security validation for text fields
    text_fields = ['name', 'description', 'ingredients', 'categories']
    for field in text_fields:
        if field in recipe_data and recipe_data[field]:
            text_value = str(recipe_data[field])
            
            xss_result = SecurityValidator.validate_input_against_xss(text_value)
            all_results.append(xss_result)
            
            sql_result = SecurityValidator.validate_input_against_sql_injection(text_value)
            all_results.append(sql_result)
    
    return APIValidator._create_validation_report(all_results)

def validate_api_request_comprehensive(endpoint: str, 
                                     payload: Dict[str, Any],
                                     headers: Dict[str, str] = None) -> ValidationReport:
    """
    Komplex API kérés validálása
    
    Args:
        endpoint: API endpoint neve
        payload: Kérés payload
        headers: HTTP headers
        
    Returns:
        ValidationReport objektum
    """
    all_results = []
    
    # Endpoint-specific validation
    if endpoint == 'rate':
        rating_report = APIValidator.validate_rating_request(payload)
        all_results.extend(rating_report.results)
    elif endpoint == 'search':
        search_report = APIValidator.validate_search_request(payload)
        all_results.extend(search_report.results)
    elif endpoint == 'recommend':
        recommend_report = APIValidator.validate_recommendation_request(payload)
        all_results.extend(recommend_report.results)
    
    # General security validation
    for key, value in payload.items():
        if isinstance(value, str):
            xss_result = SecurityValidator.validate_input_against_xss(value)
            if not xss_result.is_valid:
                all_results.append(xss_result)
            
            sql_result = SecurityValidator.validate_input_against_sql_injection(value)
            if not sql_result.is_valid:
                all_results.append(sql_result)
    
    # Headers validation (if provided)
    if headers:
        # Check for required headers
        if 'Content-Type' not in headers:
            all_results.append(ValidationResult(
                is_valid=False,
                level=ValidationLevel.WARNING,
                message="Missing Content-Type header",
                field="headers",
                error_code="MISSING_CONTENT_TYPE"
            ))
        
        # Check for suspicious User-Agent
        if 'User-Agent' in headers:
            user_agent = headers['User-Agent']
            if any(bot in user_agent.lower() for bot in ['bot', 'crawler', 'spider']):
                all_results.append(ValidationResult(
                    is_valid=True,
                    level=ValidationLevel.INFO,
                    message="Request from bot/crawler detected",
                    field="user_agent",
                    value=user_agent
                ))
    
    return APIValidator._create_validation_report(all_results)

def validate_system_configuration(config: Dict[str, Any]) -> ValidationReport:
    """
    Rendszer konfiguráció validálása
    
    Args:
        config: Konfigurációs dictionary
        
    Returns:
        ValidationReport objektum
    """
    results = []
    
    # Check required configuration keys
    required_config_keys = [
        'SECRET_KEY', 'DATABASE_URL', 'TFIDF_MAX_FEATURES',
        'SUSTAINABILITY_WEIGHT', 'HEALTH_WEIGHT', 'POPULARITY_WEIGHT'
    ]
    
    for key in required_config_keys:
        if key not in config:
            results.append(ValidationResult(
                is_valid=False,
                level=ValidationLevel.ERROR,
                message=f"Missing required configuration: {key}",
                field=key,
                error_code=f"MISSING_CONFIG_{key}"
            ))
    
    # Validate specific configuration values
    if 'SECRET_KEY' in config:
        secret_key = config['SECRET_KEY']
        if len(secret_key) < 32:
            results.append(ValidationResult(
                is_valid=False,
                level=ValidationLevel.CRITICAL,
                message=f"SECRET_KEY too short: {len(secret_key)} characters (min 32)",
                field="SECRET_KEY",
                error_code="SECRET_KEY_TOO_SHORT"
            ))
        
        if secret_key == 'dev-secret-key-change-in-production':
            results.append(ValidationResult(
                is_valid=False,
                level=ValidationLevel.CRITICAL,
                message="Using default SECRET_KEY in production",
                field="SECRET_KEY",
                error_code="DEFAULT_SECRET_KEY"
            ))
    
    # Validate weight configuration
    weight_keys = ['SUSTAINABILITY_WEIGHT', 'HEALTH_WEIGHT', 'POPULARITY_WEIGHT']
    if all(key in config for key in weight_keys):
        total_weight = sum(config[key] for key in weight_keys)
        if abs(total_weight - 1.0) > 0.001:
            results.append(ValidationResult(
                is_valid=False,
                level=ValidationLevel.ERROR,
                message=f"Weights don't sum to 1.0: {total_weight}",
                field="weights",
                value=total_weight,
                error_code="WEIGHTS_SUM_INVALID"
            ))
    
    return APIValidator._create_validation_report(results)

# =====================================
# Export Functions
# =====================================

__all__ = [
    # Classes
    'ValidationLevel', 'ValidationResult', 'ValidationReport',
    'InputValidator', 'APIValidator', 'DataStructureValidator', 'SecurityValidator',
    
    # Comprehensive validation functions
    'validate_complete_recipe_submission', 'validate_api_request_comprehensive', 
    'validate_system_configuration'
]
