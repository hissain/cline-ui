import os
import json
import threading
from flask import Flask, render_template, request, jsonify
from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.ext.declarative import declarative_base
from . import cline_client

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cline_ui.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Database setup
Base = declarative_base()
engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'])
session_factory = sessionmaker(bind=engine)
Session = scoped_session(session_factory)

class QueryHistory(Base):
    __tablename__ = 'query_history'

    id = Column(Integer, primary_key=True)
    query = Column(Text, nullable=False)
    response = Column(Text, nullable=False)
    search_options = Column(String(255))
    task_id = Column(String(50), nullable=True)

Base.metadata.create_all(engine)

@app.teardown_appcontext
def shutdown_session(exception=None):
    Session.remove()

def run_query_background(history_id, query_text, task_id=None):
    with app.app_context():
        local_session = session_factory()
        
        def update_status(status_text):
            try:
                # Re-query the item to ensure it's attached to session
                item = local_session.query(QueryHistory).get(history_id)
                if item:
                    item.response = status_text
                    local_session.commit()
            except Exception as e:
                print(f"Error updating status: {e}")
                local_session.rollback()

        try:
            # Context Stuffing: Prepend previous history if resuming, instead of using `task open`
            final_query = query_text
            if task_id:
                # Find the item associated with this task_id (most recent one)
                parent_item = local_session.query(QueryHistory).filter_by(task_id=task_id).order_by(QueryHistory.id.desc()).first()
                if parent_item:
                    context = f"Context from previous conversation (Task {task_id}):\n"
                    context += f"User: {parent_item.query}\n"
                    context += f"Assistant: {parent_item.response}\n\n"
                    final_query = context + "New Request: " + query_text
            
            # Run as new task (pass task_id=None) to avoid `cline task open` issues
            result = cline_client.run_cline_command(final_query, update_callback=update_status, task_id=None)
            
            history_item = local_session.query(QueryHistory).get(history_id)
            if history_item:
                history_item.response = result["response"]
                if result.get("task_id"):
                    history_item.task_id = result["task_id"]
                local_session.commit()
        except Exception as e:
            print(f"Error in background task: {e}")
            history_item = local_session.query(QueryHistory).get(history_id)
            if history_item:
                history_item.response = f"Error: {str(e)}"
                local_session.commit()
        finally:
            local_session.close()

# Routes
@app.route('/')
def index():
    history = Session.query(QueryHistory).order_by(QueryHistory.id.desc()).all()
    return render_template('index.html', history=history)

@app.route('/query', methods=['POST'])
def query():
    query_text = request.form.get('query')
    search_options = request.form.get('search_options')
    task_id = request.form.get('task_id')
    
    # Create initial entry
    new_query = QueryHistory(query=query_text, response="Processing...", search_options=search_options, task_id=task_id)
    Session.add(new_query)
    Session.commit()
    
    # Start background task
    thread = threading.Thread(target=run_query_background, args=(new_query.id, query_text, task_id))
    thread.start()

    return jsonify({'response': "Processing...", 'id': new_query.id})

@app.route('/history/<int:item_id>', methods=['GET', 'DELETE'])
def handle_history_item(item_id):
    if request.method == 'DELETE':
        try:
            item = Session.query(QueryHistory).get(item_id)
            if item:
                Session.delete(item)
                Session.commit()
                return jsonify({'success': True})
            return jsonify({'success': False, 'message': 'Item not found'})
        except Exception as e:
            Session.rollback()
            return jsonify({'success': False, 'message': str(e)})
    elif request.method == 'GET':
        item = Session.query(QueryHistory).get(item_id)
        if item:
            return jsonify({
                'id': item.id, 
                'query': item.query, 
                'response': item.response,
                'task_id': item.task_id
            })
        return jsonify({'error': 'Item not found'}), 404

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    settings_path = os.path.join(os.path.dirname(__file__), 'settings.json')
    if request.method == 'POST':
        cline_path = request.form.get('cline_path')
        with open(settings_path, 'w') as f:
            json.dump({'cline_path': cline_path}, f)
        return jsonify({'message': 'Settings saved!'})
    
    cline_path = cline_client.get_cline_path()
            
    return render_template('settings.html', cline_path=cline_path)
