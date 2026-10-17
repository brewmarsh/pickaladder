from typing import Any
import random

from firebase_admin import auth, firestore

try:
    from faker import Faker
except ImportError:
    Faker = None  # type: ignore

def generate_fake_users(count: int = 10) -> list[dict[str, Any]]:
    if Faker is None:
        raise ImportError("Faker package is not installed.")

    db, fake, new_users = firestore.client(), Faker(), []
    for _ in range(count):
        email, password = (
            fake.email(),
            fake.password(
                length=12,
                special_chars=True,
                digits=True,
                upper_case=True,
                lower_case=True,
            ),
        )
        user_record = auth.create_user(email=email, password=password)
        user_doc = {
            "username": fake.user_name(),
            "email": email,
            "name": fake.name(),
            "duprRating": round(random.uniform(2.5, 7.0), 2),  # nosec B311
            "isAdmin": False,
            "createdAt": firestore.SERVER_TIMESTAMP,
        }
        db.collection("users").document(user_record.uid).set(user_doc)
        new_users.append({"uid": user_record.uid, **user_doc})
    return new_users
