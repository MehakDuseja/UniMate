from __future__ import annotations

from pydantic import BaseModel, Field
from typing import List, Optional


class UniversityDepartmentData(BaseModel):
    university_id: str = Field(description="Canonical unique university identifier")
    university_name: str = Field(description="Official university name")
    department: str = Field(description="Department or program area")
    city: str = Field(description="City where the university is located")
    min_eligibility_percentage: Optional[float] = Field(
        None,
        description="Minimum eligibility percentage e.g. 60.0",
    )
    entry_test_name: Optional[str] = Field(
        None,
        description="Entry test name such as NAT, ECAT, SAT, IBA Aptitude Test, HAT, NU Admission Test",
    )
    tuition_fee_amount: Optional[int] = Field(
        None,
        description="Tuition fee amount in PKR, billed per tuition_fee_period",
    )
    tuition_fee_period: Optional[str] = Field(
        None,
        description="Billing period the tuition_fee_amount is quoted in: 'per_credit_hour', 'per_semester', or 'per_year'",
    )
    has_scholarships: bool = Field(
        False,
        description="Whether the university offers any scholarships or financial assistance",
    )
    scholarship_details: Optional[str] = Field(
        "",
        description="Short scholarship summary for search and retrieval",
    )
    test_pattern_summary: Optional[str] = Field(
        "",
        description="Concise summary of the admission/test pattern",
    )
    offered_courses: List[str] = Field(
        default_factory=list,
        description="Offered course titles or programs",
    )
    fee_details: Optional[str] = Field(
        "",
        description="Concise fee structure summary",
    )
    source_pages: List[str] = Field(
        default_factory=list,
        description="URLs used to build this record",
    )
    raw_text: Optional[str] = Field(
        "",
        description="Raw text context used for embedding and verification",
    )
    hec_recognized: Optional[bool] = Field(
        None,
        description="Whether the university is a recognized, degree-granting institution per HEC Pakistan",
    )
    official_website: Optional[str] = Field(
        None,
        description="University's official website root domain, derived from scraped source URLs",
    )
    province: Optional[str] = Field(
        None,
        description="Pakistani province the university is located in",
    )
    is_public: Optional[bool] = Field(
        None,
        description="Whether the university is a public-sector institution",
    )
    hostel_available: Optional[bool] = Field(
        None,
        description="Whether the university provides (or explicitly does not provide) hostel/accommodation",
    )
    hostel_details: Optional[str] = Field(
        "",
        description="Free-text summary of hostel/accommodation arrangements",
    )
    latitude: Optional[float] = Field(
        None,
        description="Campus latitude in decimal degrees",
    )
    longitude: Optional[float] = Field(
        None,
        description="Campus longitude in decimal degrees",
    )
