from bson import ObjectId
from datetime import datetime
from .db import projects_col, templates_col, settings_col, features_col, statistics_col, testimonials_col

def serialize_doc(doc):
    if doc is None:
        return None
    doc["_id"] = str(doc["_id"])
    if "last_modified" in doc and isinstance(doc["last_modified"], datetime):
        doc["last_modified"] = doc["last_modified"].isoformat()
    return doc

def serialize_cursor(cursor):
    return [serialize_doc(doc) for doc in cursor]

# Projects CRUD
def create_project(owner_id, title, content, filename='main.tex', status='draft'):
    data = {
        "owner_id": owner_id,
        "title": title,
        "content": content,
        "filename": filename,
        "status": status,
        "last_modified": datetime.utcnow(),
        "collaborator_ids": []
    }
    result = projects_col.insert_one(data)
    return str(result.inserted_id)

def get_projects(filter_query=None, sort=None, limit=None):
    cursor = projects_col.find(filter_query or {})
    if sort:
        cursor = cursor.sort(sort)
    if limit:
        cursor = cursor.limit(limit)
    return serialize_cursor(cursor)

def get_user_projects(owner_id):
    return get_projects({"owner_id": owner_id}, sort=[("last_modified", -1)])

def get_shared_projects_count(user_id):
    return projects_col.count_documents({"collaborator_ids": user_id})

def get_project_by_id(project_id):
    doc = projects_col.find_one({"_id": ObjectId(project_id)})
    return serialize_doc(doc)

def update_project(project_id, update_data):
    update_data["last_modified"] = datetime.utcnow()
    projects_col.update_one({"_id": ObjectId(project_id)}, {"$set": update_data})

def delete_project(project_id):
    projects_col.delete_one({"_id": ObjectId(project_id)})

# Templates
def get_templates(limit=None):
    cursor = templates_col.find({})
    if limit:
        cursor = cursor.limit(limit)
    return serialize_cursor(cursor)

# Settings
def get_all_settings():
    try:
        cursor = settings_col.find({})
        settings = {doc["key"]: doc["value"] for doc in cursor}
        return settings
    except Exception as e:
        print(f"Error fetching settings: {e}")
        return {}

# Features
def get_features():
    return serialize_cursor(features_col.find({}).sort("order", 1))

# Statistics
def get_statistics():
    return serialize_cursor(statistics_col.find({}).sort("order", 1))

# Testimonials
def get_testimonials():
    return serialize_cursor(testimonials_col.find({}))
