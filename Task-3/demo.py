"""
Task-3/demo.py
==============
End-to-end demonstration of the custom ORM.

Run with:
    python demo.py

The script uses an in-memory SQLite database so it leaves no files on disk.
Every SQL statement is printed with a cyan "SQL:" prefix.
"""

from __future__ import annotations

import sys
import io

# Ensure stdout can handle UTF-8 on Windows terminals
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import textwrap

# ── Banner helper ─────────────────────────────────────────────────────────────

def section(title: str) -> None:
    width = 72
    print()
    print("=" * width)
    print(f"  {title}")
    print("=" * width)


def subsection(title: str) -> None:
    print(f"\n-- {title} {'-' * max(0, 64 - len(title))}")   


# ─────────────────────────────────────────────────────────────────────────────
# ORM setup
# ─────────────────────────────────────────────────────────────────────────────

from orm import (
    BooleanField,
    CharField,
    Database,
    FloatField,
    ForeignKey,
    IntegerField,
    Model,
    TextField,
    ValidationError,
)

# Connect to an in-memory database
Database.connect(":memory:")
Database.echo = True     # print every SQL statement


# ─────────────────────────────────────────────────────────────────────────────
# 1. Model definitions
# ─────────────────────────────────────────────────────────────────────────────

section("1. Model Definitions  (metaclass + descriptor introspection)")

class User(Model):
    """Application user with profile fields."""
    name      = CharField(max_length=100)
    email     = CharField(max_length=255, unique=True)
    age       = IntegerField(nullable=True)
    bio       = TextField(nullable=True)
    is_active = BooleanField(nullable=True, default=True)


class Category(Model):
    """Blog post category."""
    name = CharField(max_length=50, unique=True)


class Post(Model):
    """Blog post authored by a User and belonging to a Category."""
    title    = CharField(max_length=200)
    body     = TextField(nullable=True)
    rating   = FloatField(nullable=True)
    author   = ForeignKey(User, related_name="posts")
    category = ForeignKey(Category, related_name="posts", nullable=True)


class Comment(Model):
    """Comment on a Post by a User."""
    content    = TextField()
    post       = ForeignKey(Post, related_name="comments")
    commenter  = ForeignKey(User, related_name="comments")


# Pretty-print the discovered field metadata
for model_cls in (User, Category, Post, Comment):
    print(f"\n{model_cls.__name__}  (table: '{model_cls._meta['table_name']}')")
    for attr, field in model_cls._meta["fields"]:
        print(f"    {attr:20s} → {field!r}")


# ─────────────────────────────────────────────────────────────────────────────
# 2. CREATE TABLE (DDL generation)
# ─────────────────────────────────────────────────────────────────────────────

section("2. CREATE TABLE  (auto-generated DDL)")

User.create_table()
Category.create_table()
Post.create_table()
Comment.create_table()


# ─────────────────────────────────────────────────────────────────────────────
# 3. INSERT – save() → INSERT path
# ─────────────────────────────────────────────────────────────────────────────

section("3. INSERT via .save()")

subsection("Create users")
alice = User(name="Alice", email="alice@example.com", age=30)
alice.save()

bob = User(name="Bob", email="bob@example.com", age=25)
bob.save()

carol = User(name="Carol", email="carol@example.com", age=22)
carol.save()

dave = User(name="Dave", email="dave@example.com", age=35, is_active=False)
dave.save()

subsection("Create categories")
tech = Category.create(name="Technology")
life = Category.create(name="Lifestyle")

subsection("Create posts")
p1 = Post(title="Hello World", body="My first post.", rating=4.5, author=alice, category=tech)
p1.save()

p2 = Post(title="Python Tips", body="Some cool tips.", rating=4.8, author=alice, category=tech)
p2.save()

p3 = Post(title="Morning Routine", body="How I start my day.", rating=3.9, author=bob, category=life)
p3.save()

p4 = Post(title="Advanced Metaclasses", body="Deep dive into metaclasses.", rating=5.0, author=dave, category=tech)
p4.save()

subsection("Create comments")
Comment.create(content="Great post!", post=p1, commenter=bob)
Comment.create(content="Very helpful.", post=p1, commenter=carol)
Comment.create(content="Nice one!", post=p2, commenter=carol)


# ─────────────────────────────────────────────────────────────────────────────
# 4. SELECT – QuerySet chains
# ─────────────────────────────────────────────────────────────────────────────

section("4. QuerySet  (filter · order_by · limit · chaining)")

subsection("All users")
all_users = User.all()
print(all_users)

subsection("Users aged >= 25, ordered by name DESC")
users = User.filter(age__gte=25).order_by("-name").all()
print(users)

subsection("Users aged between 24 and 32 (inclusive)")
users = User.filter(age__gte=24).filter(age__lte=32).all()
print(users)

subsection("Users with name LIKE 'A%'")
users = User.filter(name__like="A%").all()
print(users)

subsection("Exclude inactive users (is_active=False)")
active = User.exclude(is_active=False).all()
print(active)

subsection("User IN list of names")
subset = User.filter(name__in=["Alice", "Carol"]).all()
print(subset)

subsection("Users where bio IS NULL")
no_bio = User.filter(bio__isnull=True).all()
print(no_bio)

subsection("All posts ordered by rating DESC, limit 3")
top_posts = Post.order_by("-rating").limit(3).all()
print(top_posts)

subsection(".first() and .last()")
print("First (by default order):", User.order_by("name").first())
print("Last  (by default order):", User.order_by("name").last())

subsection(".count()")
print("Total users:", User.count())
print("Active users:", User.exclude(is_active=False).count())

subsection(".exists()")
print("Any user named Alice?", User.filter(name="Alice").exists())
print("Any user named Zara? ", User.filter(name="Zara").exists())


# ─────────────────────────────────────────────────────────────────────────────
# 5. GET – unique retrieval
# ─────────────────────────────────────────────────────────────────────────────

section("5. Model.get()  (unique-row retrieval)")

subsection("Get alice by email")
fetched_alice = User.get(email="alice@example.com")
print(fetched_alice)

subsection("DoesNotExist exception")
try:
    User.get(name="Nobody")
except User.DoesNotExist as exc:
    print(f"Caught DoesNotExist: {exc}")

subsection("MultipleObjectsReturned exception")
try:
    User.get(is_active=True)
except User.MultipleObjectsReturned as exc:
    print(f"Caught MultipleObjectsReturned: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# 6. UPDATE – save() → UPDATE path
# ─────────────────────────────────────────────────────────────────────────────

section("6. UPDATE via .save()  (UPDATE path when id is set)")

subsection("Update Alice's age to 31")
alice.age = 31
alice.save()

subsection("Bulk update via QuerySet.update()")
updated = User.filter(is_active=False).update(is_active=True)
print(f"Rows updated: {updated}")


# ─────────────────────────────────────────────────────────────────────────────
# 7. DELETE
# ─────────────────────────────────────────────────────────────────────────────

section("7. DELETE")

subsection("Delete carol (instance.delete())")
carol_id = carol.id
carol.delete()
print(f"Carol's id after delete: {carol.id}")

subsection("Bulk delete via QuerySet.delete()")
# Re-create carol so we can bulk-delete her again
temp = User.create(name="Temp", email="temp@example.com", age=20)
deleted = User.filter(name="Temp").delete()
print(f"Rows deleted: {deleted}")


# ─────────────────────────────────────────────────────────────────────────────
# 8. Lazy-loaded ForeignKey reverse relations
# ─────────────────────────────────────────────────────────────────────────────

section("8. Lazy-loaded Reverse Relations  (related_name)")

subsection("alice.posts  →  lazy SQL on access")
alice_posts = alice.posts       # triggers SELECT * FROM post WHERE author_id = ?
print(alice_posts)

subsection("p1.comments  →  lazy SQL on access")
p1_comments = p1.comments
print(p1_comments)

subsection("tech.posts  →  all posts in tech category")
tech_posts = tech.posts
print(tech_posts)


# ─────────────────────────────────────────────────────────────────────────────
# 9. Field validation
# ─────────────────────────────────────────────────────────────────────────────

section("9. Field Validation")

subsection("CharField max_length violation")
try:
    bad = User(name="A" * 200, email="x@y.com", age=1)
except ValidationError as exc:
    print(f"Caught ValidationError: {exc}")

subsection("IntegerField type coercion (string '42' → int 42)")
u = User(name="Test", email="test@example.com", age="42")
print(f"age type: {type(u.age).__name__!r}, value: {u.age}")

subsection("NOT NULL violation")
try:
    bad = User(name=None, email="n@n.com")
except ValidationError as exc:
    print(f"Caught ValidationError: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# 10. to_dict + refresh
# ─────────────────────────────────────────────────────────────────────────────

section("10. to_dict()  and  refresh()")

subsection("alice.to_dict()")
import json
print(json.dumps(alice.to_dict(), indent=2, default=str))

subsection("refresh() reloads from DB")
alice.name = "MODIFIED_IN_MEMORY"
print(f"Before refresh: {alice.name!r}")
alice.refresh()
print(f"After  refresh: {alice.name!r}")


# ─────────────────────────────────────────────────────────────────────────────
# 11. sql() – inspect generated SQL without running it
# ─────────────────────────────────────────────────────────────────────────────

section("11. QuerySet.sql()  (inspect SQL without executing)")

qs = User.filter(age__gte=25).order_by("-name").limit(5)
Database.echo = False          # suppress the actual execution logging
print("SQL preview:", qs.sql())
Database.echo = True


# ─────────────────────────────────────────────────────────────────────────────
# 12. DROP TABLE
# ─────────────────────────────────────────────────────────────────────────────

section("12. DROP TABLE")

Comment.drop_table()
Post.drop_table()
Category.drop_table()
User.drop_table()


# ─────────────────────────────────────────────────────────────────────────────
print()
print("=" * 72)
print("  [OK] All demonstrations completed successfully.")
print("=" * 72)
print()
