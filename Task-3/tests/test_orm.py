"""
Task-3/tests/test_orm.py
═════════════════════════
Comprehensive unit + integration tests for the custom ORM.

Run with:
    pytest tests/ -v
    pytest tests/ -v --tb=short
"""

from __future__ import annotations

import pytest

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


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def fresh_db():
    """
    Before each test:
      1. Connect to a fresh in-memory database.
      2. Silence SQL echo to keep test output clean.
    """
    Database.connect(":memory:")
    Database.echo = False
    yield
    Database.close()


# ── Shared models (defined once at module level) ───────────────────────────────
# We define them outside fixtures so the metaclass runs once.
# The DB is recreated per-test via fresh_db, but the Python class objects persist.

class Author(Model):
    name  = CharField(max_length=100)
    email = CharField(max_length=255, unique=True)
    age   = IntegerField(nullable=True)
    score = FloatField(nullable=True)
    active = BooleanField(nullable=True, default=True)
    bio   = TextField(nullable=True)


class Tag(Model):
    name = CharField(max_length=50)


class Article(Model):
    title  = CharField(max_length=200)
    body   = TextField(nullable=True)
    author = ForeignKey(Author, related_name="articles")
    tag    = ForeignKey(Tag, related_name="articles", nullable=True)


@pytest.fixture()
def tables():
    """Create all tables in the fresh in-memory db."""
    Author.create_table()
    Tag.create_table()
    Article.create_table()


@pytest.fixture()
def sample_data(tables):
    """Populate sample rows and return a namespace dict."""
    alice = Author.create(name="Alice", email="alice@test.com", age=30, score=9.5)
    bob   = Author.create(name="Bob",   email="bob@test.com",   age=25, score=7.0)
    carol = Author.create(name="Carol", email="carol@test.com", age=22, score=8.2)
    dave  = Author.create(name="Dave",  email="dave@test.com",  age=35, active=False)

    tag_py = Tag.create(name="Python")
    tag_web = Tag.create(name="Web")

    a1 = Article.create(title="Intro to Python", body="...", author=alice, tag=tag_py)
    a2 = Article.create(title="Advanced Python", body="...", author=alice, tag=tag_py)
    a3 = Article.create(title="Web Frameworks",  body="...", author=bob,   tag=tag_web)

    return {
        "alice": alice, "bob": bob, "carol": carol, "dave": dave,
        "tag_py": tag_py, "tag_web": tag_web,
        "a1": a1, "a2": a2, "a3": a3,
    }


# ──────────────────────────────────────────────────────────────────────────────
# 1. Metaclass & _meta
# ──────────────────────────────────────────────────────────────────────────────

class TestMetaclass:
    def test_table_name_snake_case(self):
        assert Author._meta["table_name"] == "author"
        assert Article._meta["table_name"] == "article"

    def test_id_field_injected(self):
        field_names = [attr for attr, _ in Author._meta["fields"]]
        assert "id" in field_names
        assert field_names[0] == "id"         # always first

    def test_fields_ordered_by_declaration(self):
        field_names = [attr for attr, _ in Author._meta["fields"]]
        # id → name → email → age → score → active → bio
        assert field_names == ["id", "name", "email", "age", "score", "active", "bio"]

    def test_fk_column_name_suffixed(self):
        col_map = Article._meta["column_map"]
        assert "author_id" in col_map
        assert "tag_id" in col_map

    def test_model_registry(self):
        from orm import ModelRegistry
        assert "Author" in ModelRegistry.all()
        assert "Article" in ModelRegistry.all()


# ──────────────────────────────────────────────────────────────────────────────
# 2. DDL – create_table / drop_table
# ──────────────────────────────────────────────────────────────────────────────

class TestDDL:
    def test_create_table_idempotent(self, tables):
        # Should not raise on second call (IF NOT EXISTS)
        Author.create_table()

    def test_drop_table(self, tables):
        Author.drop_table()
        # Querying a dropped table should raise
        with pytest.raises(Exception):
            Author.all()

    def test_create_table_column_defs(self, tables):
        """Verify column definitions via PRAGMA table_info."""
        conn = Database.get_connection()
        pragma = conn.execute("PRAGMA table_info(author);").fetchall()
        col_names = [row["name"] for row in pragma]
        assert "id" in col_names
        assert "name" in col_names
        assert "email" in col_names
        assert "age" in col_names

    def test_foreign_key_pragma(self, tables):
        conn = Database.get_connection()
        fk_list = conn.execute("PRAGMA foreign_key_list(article);").fetchall()
        referred_tables = {row["table"] for row in fk_list}
        assert "author" in referred_tables


# ──────────────────────────────────────────────────────────────────────────────
# 3. Field descriptors & validation
# ──────────────────────────────────────────────────────────────────────────────

class TestFieldValidation:
    def test_charfield_max_length(self):
        with pytest.raises(ValidationError, match="max_length"):
            Author(name="x" * 200, email="a@b.com")

    def test_charfield_coerces_to_str(self):
        a = Author(name=42, email="a@b.com")
        assert isinstance(a.name, str)
        assert a.name == "42"

    def test_integerfield_coerces_string(self):
        a = Author(name="X", email="x@x.com", age="99")
        assert a.age == 99

    def test_integerfield_rejects_garbage(self):
        with pytest.raises(ValidationError):
            Author(name="X", email="x@x.com", age="not-a-number")

    def test_floatfield_coerces_int(self):
        a = Author(name="X", email="x@x.com", score=5)
        assert isinstance(a.score, float)

    def test_not_null_violation(self):
        with pytest.raises(ValidationError):
            Author(name=None, email="x@x.com")

    def test_nullable_accepts_none(self, tables):
        a = Author(name="X", email="x@x.com", age=None)
        a.save()
        fetched = Author.get(email="x@x.com")
        assert fetched.age is None

    def test_boolean_default(self, tables):
        a = Author.create(name="Y", email="y@y.com")
        assert a.active is True    # default=True

    def test_fk_accepts_instance(self, tables):
        alice = Author.create(name="Alice", email="a@a.com")
        tag   = Tag.create(name="T")
        art   = Article(title="T", author=alice, tag=tag)
        # author should be stored as integer id
        assert art.__dict__["author"] == alice.id

    def test_fk_accepts_int(self, tables):
        alice = Author.create(name="Alice", email="a@a.com")
        art   = Article(title="T", author=alice.id)
        assert art.__dict__["author"] == alice.id


# ──────────────────────────────────────────────────────────────────────────────
# 4. INSERT / save()
# ──────────────────────────────────────────────────────────────────────────────

class TestInsert:
    def test_save_sets_id(self, tables):
        a = Author(name="Test", email="t@t.com")
        assert a.id is None
        a.save()
        assert a.id is not None

    def test_id_autoincrement(self, tables):
        a1 = Author.create(name="A", email="a@a.com")
        a2 = Author.create(name="B", email="b@b.com")
        assert a2.id == a1.id + 1

    def test_create_shorthand(self, tables):
        a = Author.create(name="C", email="c@c.com", age=20)
        assert a.id is not None
        assert Author.get(email="c@c.com").name == "C"


# ──────────────────────────────────────────────────────────────────────────────
# 5. SELECT / QuerySet
# ──────────────────────────────────────────────────────────────────────────────

class TestQuerySet:
    def test_all(self, sample_data):
        all_authors = Author.all()
        assert len(all_authors) == 4

    def test_filter_eq(self, sample_data):
        results = Author.filter(name="Alice").all()
        assert len(results) == 1
        assert results[0].name == "Alice"

    def test_filter_gte(self, sample_data):
        results = Author.filter(age__gte=25).all()
        assert all(a.age >= 25 for a in results if a.age is not None)

    def test_filter_lte(self, sample_data):
        results = Author.filter(age__lte=30).all()
        ages = [a.age for a in results if a.age is not None]
        assert all(age <= 30 for age in ages)

    def test_filter_lt(self, sample_data):
        results = Author.filter(age__lt=25).all()
        assert all(a.age < 25 for a in results if a.age is not None)

    def test_filter_gt(self, sample_data):
        results = Author.filter(age__gt=25).all()
        assert all(a.age > 25 for a in results if a.age is not None)

    def test_filter_ne(self, sample_data):
        results = Author.filter(name__ne="Alice").all()
        assert all(a.name != "Alice" for a in results)

    def test_filter_like(self, sample_data):
        results = Author.filter(name__like="A%").all()
        assert all(a.name.startswith("A") for a in results)

    def test_filter_ilike(self, sample_data):
        results = Author.filter(name__ilike="alice").all()
        assert len(results) == 1

    def test_filter_in(self, sample_data):
        results = Author.filter(name__in=["Alice", "Bob"]).all()
        assert {a.name for a in results} == {"Alice", "Bob"}

    def test_filter_in_empty(self, sample_data):
        results = Author.filter(name__in=[]).all()
        assert results == []

    def test_filter_isnull_true(self, sample_data):
        results = Author.filter(bio__isnull=True).all()
        assert all(a.bio is None for a in results)

    def test_filter_isnull_false(self, tables):
        Author.create(name="X", email="x@x.com", bio="My bio")
        Author.create(name="Y", email="y@y.com")
        results = Author.filter(bio__isnull=False).all()
        assert len(results) == 1

    def test_exclude(self, sample_data):
        results = Author.exclude(active=False).all()
        assert all(a.active != False for a in results)

    def test_chained_filters(self, sample_data):
        results = Author.filter(age__gte=25).filter(age__lte=30).all()
        assert all(25 <= a.age <= 30 for a in results if a.age is not None)

    def test_order_by_asc(self, sample_data):
        results = Author.order_by("name").all()
        names = [a.name for a in results]
        assert names == sorted(names)

    def test_order_by_desc(self, sample_data):
        results = Author.filter(age__gte=1).order_by("-age").all()
        ages = [a.age for a in results]
        assert ages == sorted(ages, reverse=True)

    def test_order_by_multi(self, sample_data):
        results = Author.order_by("active", "-name").all()
        # Just verify it executes without error
        assert len(results) == 4

    def test_limit(self, sample_data):
        results = Author.order_by("name").limit(2).all()
        assert len(results) == 2

    def test_offset(self, sample_data):
        all_ordered = Author.order_by("name").all()
        offset_results = Author.order_by("name").offset(2).all()
        assert offset_results == all_ordered[2:]

    def test_limit_offset(self, sample_data):
        page = Author.order_by("id").limit(2).offset(1).all()
        assert len(page) == 2

    def test_first(self, sample_data):
        first = Author.order_by("name").first()
        assert first is not None
        assert first.name == "Alice"

    def test_last(self, sample_data):
        last = Author.order_by("name").last()
        assert last is not None
        assert last.name == "Dave"

    def test_first_none(self, tables):
        result = Author.filter(name="Nobody").first()
        assert result is None

    def test_count(self, sample_data):
        assert Author.count() == 4
        assert Author.filter(age__gte=25).count() == 3

    def test_exists_true(self, sample_data):
        assert Author.filter(name="Alice").exists() is True

    def test_exists_false(self, sample_data):
        assert Author.filter(name="Nobody").exists() is False

    def test_queryset_iterable(self, sample_data):
        names = [a.name for a in Author.order_by("name")]
        assert names == ["Alice", "Bob", "Carol", "Dave"]

    def test_queryset_len(self, sample_data):
        assert len(Author.filter(age__gte=25)) == 3

    def test_queryset_getitem(self, sample_data):
        qs = Author.order_by("name")
        assert qs[0].name == "Alice"

    def test_sql_preview(self, sample_data):
        sql = Author.filter(age__gte=25).order_by("-name").sql()
        assert "SELECT" in sql
        assert "WHERE" in sql
        assert "ORDER BY" in sql

    def test_clone_independence(self, sample_data):
        base = Author.filter(age__gte=20)
        narrow = base.filter(name="Alice")
        # base should still return 4 (age__gte=20), narrow returns 1
        assert base.count() == 4
        assert narrow.count() == 1


# ──────────────────────────────────────────────────────────────────────────────
# 6. GET
# ──────────────────────────────────────────────────────────────────────────────

class TestGet:
    def test_get_by_field(self, sample_data):
        a = Author.get(email="alice@test.com")
        assert a.name == "Alice"

    def test_get_does_not_exist(self, sample_data):
        with pytest.raises(Author.DoesNotExist):
            Author.get(name="Nobody")

    def test_get_multiple_objects(self, sample_data):
        with pytest.raises(Author.MultipleObjectsReturned):
            Author.get(active=True)


# ──────────────────────────────────────────────────────────────────────────────
# 7. UPDATE
# ──────────────────────────────────────────────────────────────────────────────

class TestUpdate:
    def test_save_updates_existing(self, sample_data):
        alice = sample_data["alice"]
        alice.age = 99
        alice.save()
        fetched = Author.get(email="alice@test.com")
        assert fetched.age == 99

    def test_bulk_update(self, sample_data):
        rows = Author.filter(active=False).update(active=True)
        assert rows == 1
        assert Author.filter(active=False).count() == 0

    def test_refresh(self, sample_data):
        alice = sample_data["alice"]
        alice.__dict__["name"] = "MODIFIED"
        alice.refresh()
        assert alice.name == "Alice"


# ──────────────────────────────────────────────────────────────────────────────
# 8. DELETE
# ──────────────────────────────────────────────────────────────────────────────

class TestDelete:
    def test_instance_delete(self, sample_data):
        carol = sample_data["carol"]
        carol.delete()
        assert carol.id is None
        assert Author.filter(name="Carol").count() == 0

    def test_delete_raises_if_unsaved(self):
        a = Author(name="X", email="x@x.com")
        with pytest.raises(RuntimeError):
            a.delete()

    def test_queryset_delete(self, sample_data):
        count = Author.filter(age__lt=25).delete()
        assert count >= 0
        assert Author.filter(age__lt=25).count() == 0


# ──────────────────────────────────────────────────────────────────────────────
# 9. ForeignKey & reverse relations (lazy loading)
# ──────────────────────────────────────────────────────────────────────────────

class TestForeignKey:
    def test_reverse_relation(self, sample_data):
        alice = sample_data["alice"]
        articles = alice.articles       # lazy SQL
        assert len(articles) == 2
        assert all(a.__dict__["author"] == alice.id for a in articles)

    def test_reverse_relation_tag(self, sample_data):
        tag_py = sample_data["tag_py"]
        articles = tag_py.articles
        assert len(articles) == 2

    def test_fk_stores_id(self, sample_data):
        a1 = sample_data["a1"]
        alice = sample_data["alice"]
        assert a1.__dict__["author"] == alice.id

    def test_reverse_unsaved_raises(self, tables):
        author = Author(name="Ghost", email="ghost@test.com")
        with pytest.raises(RuntimeError, match="unsaved"):
            _ = author.articles


# ──────────────────────────────────────────────────────────────────────────────
# 10. to_dict
# ──────────────────────────────────────────────────────────────────────────────

class TestToDict:
    def test_to_dict_keys(self, sample_data):
        alice = sample_data["alice"]
        d = alice.to_dict()
        assert "id" in d
        assert "name" in d
        assert "email" in d

    def test_to_dict_values(self, sample_data):
        alice = sample_data["alice"]
        d = alice.to_dict()
        assert d["name"] == "Alice"
        assert d["email"] == "alice@test.com"

    def test_fk_to_dict_uses_column_name(self, sample_data):
        a1 = sample_data["a1"]
        d = a1.to_dict()
        # FK column should be author_id, not author
        assert "author_id" in d


# ──────────────────────────────────────────────────────────────────────────────
# 11. Equality & hashing
# ──────────────────────────────────────────────────────────────────────────────

class TestEquality:
    def test_same_id_equal(self, sample_data):
        alice1 = Author.get(email="alice@test.com")
        alice2 = Author.get(email="alice@test.com")
        assert alice1 == alice2

    def test_different_id_not_equal(self, sample_data):
        alice = sample_data["alice"]
        bob   = sample_data["bob"]
        assert alice != bob

    def test_in_set(self, sample_data):
        alice = Author.get(email="alice@test.com")
        s = {alice}
        alice2 = Author.get(email="alice@test.com")
        assert alice2 in s
