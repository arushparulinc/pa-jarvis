-----------------------------
-- BUILD CONFIGURATIONS DATA 
-----------------------------

-- psql -U postgres -v target_db="pa-jarvis-dev" -f "C:\apinc\pgsql\pa-jarvis-db-inserts.sql"
-- psql -U postgres -v target_db="pa-jarvis-prd" -f "C:\apinc\pgsql\pa-jarvis-db-inserts.sql"


-- CONNECT TO DATABASE
\c :target_db


-- ADD AGENTS
INSERT INTO config.agents(agent_id, agent_name, agent_description) VALUES(1, 'Master Router Agent', 'Receives all chat requests from user and routes to the correct agent for action');
INSERT INTO config.agents(agent_id, agent_name, agent_description) VALUES(2, 'Google Drive Agent', 'Manages uploads, downloads and searches on google drive');
INSERT INTO config.agents(agent_id, agent_name, agent_description) VALUES(3, 'Personal Tools Agent', 'Executes actions for user on specific personal spaces');
INSERT INTO config.agents(agent_id, agent_name, agent_description) VALUES(4, 'Internet Tools Agent', 'Handles all internet searches and online API calls');
INSERT INTO config.agents(agent_id, agent_name, agent_description) VALUES(5, 'Comm Channels Agent', 'Sends information to various communication channels');
INSERT INTO config.agents(agent_id, agent_name, agent_description) VALUES(6, 'Planner Agent', 'Manages To-Do tasks list and calendar events');
INSERT INTO config.agents(agent_id, agent_name, agent_description) VALUES(7, 'Shopping Agent', 'Manages shopping list of items to buy');


-- ADD SYSTEM INSTRUCTIONS
INSERT INTO config.llm_system_instructions(instrc_type, instruction, instrc_priority, agent_id) VALUES('IDENTITY', 'Your name is BingaBoo', 10, 1);
INSERT INTO config.llm_system_instructions(instrc_type, instruction, instrc_priority, agent_id) VALUES('IDENTITY', 'You are a personal AI assistant that helps the user organize their digital and physical life, manage information, and automate routine tasks', 11, 1);
INSERT INTO config.llm_system_instructions(instrc_type, instruction, instrc_priority, agent_id) VALUES('PURPOSE', 'Act as Master Router Agent and use the available specialized agents as per their capabilties when required based on the user prompt', 20, 1);
INSERT INTO config.llm_system_instructions(instrc_type, instruction, instrc_priority, agent_id) VALUES('PURPOSE', 'Call the required agent as a tool call, and pass the user request prompt as parameter', 21, 1);
INSERT INTO config.llm_system_instructions(instrc_type, instruction, instrc_priority, agent_id) VALUES('AGENTS AVAILABLE', 'Google Drive Agent', 30, 1);
INSERT INTO config.llm_system_instructions(instrc_type, instruction, instrc_priority, agent_id) VALUES('AGENTS AVAILABLE', 'Personal Tools Agent', 31, 1);
INSERT INTO config.llm_system_instructions(instrc_type, instruction, instrc_priority, agent_id) VALUES('AGENTS AVAILABLE', 'Internet Tools Agent', 32, 1);
INSERT INTO config.llm_system_instructions(instrc_type, instruction, instrc_priority, agent_id) VALUES('AGENTS AVAILABLE', 'Comm Channels Agent', 33, 1);
INSERT INTO config.llm_system_instructions(instrc_type, instruction, instrc_priority, agent_id) VALUES('AGENTS AVAILABLE', 'Planner Agent', 34, 1);
INSERT INTO config.llm_system_instructions(instrc_type, instruction, instrc_priority, agent_id) VALUES('AGENTS AVAILABLE', 'Shopping Agent', 35, 1);
INSERT INTO config.llm_system_instructions(instrc_type, instruction, instrc_priority, agent_id) VALUES('USER PROFILE', 'Name: Arush Kumar', 60, 1);
INSERT INTO config.llm_system_instructions(instrc_type, instruction, instrc_priority, agent_id) VALUES('USER PROFILE', 'Email: arushkumar091@gmail.com', 61, 1);
INSERT INTO config.llm_system_instructions(instrc_type, instruction, instrc_priority, agent_id) VALUES('USER PROFILE', 'City: Brampton', 62, 1);
INSERT INTO config.llm_system_instructions(instrc_type, instruction, instrc_priority, agent_id) VALUES('USER PROFILE', 'Province: Ontario', 63, 1);
INSERT INTO config.llm_system_instructions(instrc_type, instruction, instrc_priority, agent_id) VALUES('USER PROFILE', 'Country: Canada', 64, 1);
INSERT INTO config.llm_system_instructions(instrc_type, instruction, instrc_priority, agent_id) VALUES('USER PROFILE', 'DOB: 1985-09-01', 65, 1);
INSERT INTO config.llm_system_instructions(instrc_type, instruction, instrc_priority, agent_id) VALUES('USER PROFILE', 'Gender: Male', 66, 1);
INSERT INTO config.llm_system_instructions(instrc_type, instruction, instrc_priority, agent_id) VALUES('USER PREFERENCES', 'Cusine: Indian', 67, 1);
INSERT INTO config.llm_system_instructions(instrc_type, instruction, instrc_priority, agent_id) VALUES('USER PREFERENCES', 'Color: Blue', 68, 1);
INSERT INTO config.llm_system_instructions(instrc_type, instruction, instrc_priority, agent_id) VALUES('USER PREFERENCES', 'Hobby: Video Games', 69, 1);
INSERT INTO config.llm_system_instructions(instrc_type, instruction, instrc_priority, agent_id) VALUES('RELEVANT MEMORIES', 'Currently working on building personal AI agent called PA-Jarvis', 150, 1);
INSERT INTO config.llm_system_instructions(instrc_type, instruction, instrc_priority, agent_id) VALUES('SUPPORTING FACTS', 'Software and Data Professional with 20 years experience', 100, 1);
INSERT INTO config.llm_system_instructions(instrc_type, instruction, instrc_priority, agent_id) VALUES('SUPPORTING FACTS', 'Has 6 year old son (Ronit) and 7 year old labrador (Pluto)', 101, 1);
INSERT INTO config.llm_system_instructions(instrc_type, instruction, instrc_priority, agent_id) VALUES('SUPPORTING FACTS', 'Has been married for 15 year to Parul Singla', 102, 1);
INSERT INTO config.llm_system_instructions(instrc_type, instruction, instrc_priority, agent_id) VALUES('IDENTITY', 'You are Google Drive Agent for user and in-service to the master router agent for various tasks defined in the tools list', 10, 2);
INSERT INTO config.llm_system_instructions(instrc_type, instruction, instrc_priority, agent_id) VALUES('PURPOSE', 'You are responsible for reading, writing, deleting and listing files in user Google Drive', 20, 2);
INSERT INTO config.llm_system_instructions(instrc_type, instruction, instrc_priority, agent_id) VALUES('OPERATING MODEL', 'For every incoming user request, do this: 1.Execute the right tool if all details are available in the user request 2.Respond back with a) SUCCESS & Tool Result or b) FAILURE & Error or c) Request for additional details', 50, 2);
INSERT INTO config.llm_system_instructions(instrc_type, instruction, instrc_priority, agent_id) VALUES('IDENTITY', 'You are Personal Tools Agent for user and in-service to the master router agent for various tasks defined in the tools list', 10, 3);
INSERT INTO config.llm_system_instructions(instrc_type, instruction, instrc_priority, agent_id) VALUES('PURPOSE', 'You are responsible for managing personal facts, quotes, pics, videos', 20, 3);
INSERT INTO config.llm_system_instructions(instrc_type, instruction, instrc_priority, agent_id) VALUES('OPERATING MODEL', 'For every incoming user request, do this: 1.Execute the right tool if all details are available in the user request 2.Respond back with a) SUCCESS & Tool Result or b) FAILURE & Error or c) Request for additional details', 50, 3);
INSERT INTO config.llm_system_instructions(instrc_type, instruction, instrc_priority, agent_id) VALUES('IDENTITY', 'You are Internet Tools Agent for user and in-service to the master router agent for various tasks defined in the tools list', 10, 4);
INSERT INTO config.llm_system_instructions(instrc_type, instruction, instrc_priority, agent_id) VALUES('PURPOSE', 'You are responsible for internet searches, weather and other online information', 20, 4);
INSERT INTO config.llm_system_instructions(instrc_type, instruction, instrc_priority, agent_id) VALUES('OPERATING MODEL', 'For every incoming user request, do this: 1.Execute the right tool if all details are available in the user request 2.Respond back with a) SUCCESS & Tool Result or b) FAILURE & Error or c) Request for additional details', 50, 4);
INSERT INTO config.llm_system_instructions(instrc_type, instruction, instrc_priority, agent_id) VALUES('IDENTITY', 'You are a Communication Tools Agent for user and in-service to the master router agent for various tasks defined in the tools list', 10, 5);
INSERT INTO config.llm_system_instructions(instrc_type, instruction, instrc_priority, agent_id) VALUES('PURPOSE', 'You are responsible for sending email, message and other notifications', 20, 5);
INSERT INTO config.llm_system_instructions(instrc_type, instruction, instrc_priority, agent_id) VALUES('OPERATING MODEL', 'For every incoming user request, do this: 1.Execute the right tool if all details are available in the user request 2.Respond back with a) SUCCESS & Tool Result or b) FAILURE & Error or c) Request for additional details', 50, 5);
INSERT INTO config.llm_system_instructions(instrc_type, instruction, instrc_priority, agent_id) VALUES('IDENTITY', 'You are a Planner Agent for user and in-service to the master router agent for various tasks defined in the tools list', 10, 6);
INSERT INTO config.llm_system_instructions(instrc_type, instruction, instrc_priority, agent_id) VALUES('PURPOSE', 'You are responsible for managing To-Do tasks list and calendar events', 20, 6);
INSERT INTO config.llm_system_instructions(instrc_type, instruction, instrc_priority, agent_id) VALUES('OPERATING MODEL', 'For every incoming user request, do this: 1.Execute the right tool if all details are available in the user request 2.Respond back with a) SUCCESS & Tool Result or b) FAILURE & Error or c) Request for additional details', 50, 6);
INSERT INTO config.llm_system_instructions(instrc_type, instruction, instrc_priority, agent_id) VALUES('IDENTITY', 'You are a Shopping Agent for user and in-service to the master router agent for various tasks defined in the tools list', 10, 7);
INSERT INTO config.llm_system_instructions(instrc_type, instruction, instrc_priority, agent_id) VALUES('PURPOSE', 'You are responsible for managing shopping list of items to buy', 20, 7);
INSERT INTO config.llm_system_instructions(instrc_type, instruction, instrc_priority, agent_id) VALUES('OPERATING MODEL', 'For every incoming user request, do this: 1.Execute the right tool if all details are available in the user request 2.Respond back with a) SUCCESS & Tool Result or b) FAILURE & Error or c) Request for additional details', 50, 7);


-- ADD TOOLS
INSERT INTO config.tools_registry(tool_id, tool_name, tool_description, agent_id) VALUES(101, 'Google Drive Agent', 'Capabilities: Upload File, Download File, Delete File, List Files in Folder', 1);
INSERT INTO config.tools_registry(tool_id, tool_name, tool_description, agent_id) VALUES(102, 'Personal Tools Agent', 'Capabilities: Manages personal facts, quotes, pics, videos', 1);
INSERT INTO config.tools_registry(tool_id, tool_name, tool_description, agent_id) VALUES(103, 'Internet Tools Agent', 'Capabilities: Google Search, Weather Information', 1);
INSERT INTO config.tools_registry(tool_id, tool_name, tool_description, agent_id) VALUES(104, 'Comm Channels Agent', 'Capabilities: Send Email', 1);
INSERT INTO config.tools_registry(tool_id, tool_name, tool_description, agent_id) VALUES(105, 'Planner Agent', 'Capabilities: Manage Calendar, To-Do Task List', 1);
INSERT INTO config.tools_registry(tool_id, tool_name, tool_description, agent_id) VALUES(106, 'Shopping Agent', 'Capabilities: Manage Shopping List', 1);
INSERT INTO config.tools_registry(tool_id, tool_name, tool_description, agent_id) VALUES(201, 'gdrive_list_folder', 'List files in a specific Google Drive folder.', 2);
INSERT INTO config.tools_registry(tool_id, tool_name, tool_description, agent_id) VALUES(202, 'gdrive_read', 'Read a specific file from Google Drive.', 2);
INSERT INTO config.tools_registry(tool_id, tool_name, tool_description, agent_id) VALUES(203, 'gdrive_write', 'Upload a local file into a specific Google Drive folder.', 2);
INSERT INTO config.tools_registry(tool_id, tool_name, tool_description, agent_id) VALUES(204, 'gdrive_delete', 'Permanently delete a specific Google Drive file.', 2);
INSERT INTO config.tools_registry(tool_id, tool_name, tool_description, agent_id) VALUES(301, 'arush_random_facts', 'Provides a random fact about Arush.', 3);
INSERT INTO config.tools_registry(tool_id, tool_name, tool_description, agent_id) VALUES(401, 'google_search', 'Search Google to answer a current or factual request.', 4);
INSERT INTO config.tools_registry(tool_id, tool_name, tool_description, agent_id) VALUES(501, 'gmail_send_email', 'Send email from gmail account of user', 5);
INSERT INTO config.tools_registry(tool_id, tool_name, tool_description, agent_id) VALUES(601, 'add_calendar_event', 'Add new event to calendar', 6);
INSERT INTO config.tools_registry(tool_id, tool_name, tool_description, agent_id) VALUES(602, 'read_calendar_event', 'Read specific event from calendar', 6);
INSERT INTO config.tools_registry(tool_id, tool_name, tool_description, agent_id) VALUES(603, 'list_calendar_events', 'List all events from calendar', 6);
INSERT INTO config.tools_registry(tool_id, tool_name, tool_description, agent_id) VALUES(604, 'delete_calendar_event', 'Delete event from calendar', 6);
INSERT INTO config.tools_registry(tool_id, tool_name, tool_description, agent_id) VALUES(605, 'add_task', 'Add task to To-Do list', 6);
INSERT INTO config.tools_registry(tool_id, tool_name, tool_description, agent_id) VALUES(606, 'get_task', 'Get specific task from To-Do list', 6);
INSERT INTO config.tools_registry(tool_id, tool_name, tool_description, agent_id) VALUES(607, 'list_tasks', 'List tasks in To-Do list', 6);
INSERT INTO config.tools_registry(tool_id, tool_name, tool_description, agent_id) VALUES(608, 'delete_task', 'Delete task from To-Do list', 6);
INSERT INTO config.tools_registry(tool_id, tool_name, tool_description, agent_id) VALUES(701, 'add_item', 'Add item to shopping list', 7);
INSERT INTO config.tools_registry(tool_id, tool_name, tool_description, agent_id) VALUES(702, 'get_item', 'Get item from shopping list', 7);
INSERT INTO config.tools_registry(tool_id, tool_name, tool_description, agent_id) VALUES(703, 'list_items', 'List items in shopping list', 7);
INSERT INTO config.tools_registry(tool_id, tool_name, tool_description, agent_id) VALUES(704, 'delete_item', 'Delete item from shopping list', 7);


-- ADD TOOL PARAMETERS
INSERT INTO config.tools_parameters(tool_id, param_name, param_type, param_description, is_required) VALUES(101, 'User Prompt', 'text', 'Latest user prompt with the request', true);
INSERT INTO config.tools_parameters(tool_id, param_name, param_type, param_description, is_required) VALUES(102, 'User Prompt', 'text', 'Latest user prompt with the request', true);
INSERT INTO config.tools_parameters(tool_id, param_name, param_type, param_description, is_required) VALUES(103, 'User Prompt', 'text', 'Latest user prompt with the request', true);
INSERT INTO config.tools_parameters(tool_id, param_name, param_type, param_description, is_required) VALUES(104, 'User Prompt', 'text', 'Latest user prompt with the request', true);
INSERT INTO config.tools_parameters(tool_id, param_name, param_type, param_description, is_required) VALUES(105, 'User Prompt', 'text', 'Latest user prompt with the request', true);
INSERT INTO config.tools_parameters(tool_id, param_name, param_type, param_description, is_required) VALUES(106, 'User Prompt', 'text', 'Latest user prompt with the request', true);
INSERT INTO config.tools_parameters(tool_id, param_name, param_type, param_description, is_required) VALUES(201, 'folder_name', 'string', 'The Google Drive folder name to list.', true);
INSERT INTO config.tools_parameters(tool_id, param_name, param_type, param_description, is_required) VALUES(401, 'request', 'string', 'The complete request to search for.', true);
INSERT INTO config.tools_parameters(tool_id, param_name, param_type, param_description, is_required) VALUES(501, 'recipient_list', 'string', 'The list of recipient email addresses', true);
INSERT INTO config.tools_parameters(tool_id, param_name, param_type, param_description, is_required) VALUES(501, 'subject_line', 'string', 'Subject line for the email', true);
INSERT INTO config.tools_parameters(tool_id, param_name, param_type, param_description, is_required) VALUES(501, 'body', 'text', 'Body of the email', true);
INSERT INTO config.tools_parameters(tool_id, param_name, param_type, param_description, is_required) VALUES(601, 'event_name', 'string', 'Name of calendar event', true);
INSERT INTO config.tools_parameters(tool_id, param_name, param_type, param_description, is_required) VALUES(601, 'event_description', 'text', 'Description of calendar event', false);
INSERT INTO config.tools_parameters(tool_id, param_name, param_type, param_description, is_required) VALUES(601, 'event_start_time', 'timestamptz', 'Start time as an ISO 8601 date-time; a time such as 20:00 means today in America/Toronto', true);
INSERT INTO config.tools_parameters(tool_id, param_name, param_type, param_description, is_required) VALUES(601, 'event_duration_hrs', 'integer', 'Event duration in hours; defaults to 1', false);
INSERT INTO config.tools_parameters(tool_id, param_name, param_type, param_description, is_required) VALUES(601, 'event_priority', 'string', 'Optional event priority', false);
INSERT INTO config.tools_parameters(tool_id, param_name, param_type, param_description, is_required) VALUES(602, 'event_name', 'string', 'Name of calendar event to read', true);
INSERT INTO config.tools_parameters(tool_id, param_name, param_type, param_description, is_required) VALUES(604, 'event_name', 'string', 'Name of calendar event to delete', true);
INSERT INTO config.tools_parameters(tool_id, param_name, param_type, param_description, is_required) VALUES(605, 'task_name', 'string', 'Name of To-Do task to add', true);
INSERT INTO config.tools_parameters(tool_id, param_name, param_type, param_description, is_required) VALUES(605, 'task_description', 'string', 'Description of To-Do task to add', false);
INSERT INTO config.tools_parameters(tool_id, param_name, param_type, param_description, is_required) VALUES(605, 'task_priority', 'string', 'Priority of To-Do task', false);
INSERT INTO config.tools_parameters(tool_id, param_name, param_type, param_description, is_required) VALUES(605, 'task_duedate', 'date', 'Due date of To-Do task', false);
INSERT INTO config.tools_parameters(tool_id, param_name, param_type, param_description, is_required) VALUES(606, 'task_name', 'string', 'Name of To-Do task to find', true);
INSERT INTO config.tools_parameters(tool_id, param_name, param_type, param_description, is_required) VALUES(608, 'task_name', 'string', 'Name of To-Do task to delete', true);
INSERT INTO config.tools_parameters(tool_id, param_name, param_type, param_description, is_required) VALUES(701, 'item_name', 'string', 'Name of item to add to shopping list', true);
INSERT INTO config.tools_parameters(tool_id, param_name, param_type, param_description, is_required) VALUES(701, 'item_description', 'string', 'Description of item to add to shopping list', false);
INSERT INTO config.tools_parameters(tool_id, param_name, param_type, param_description, is_required) VALUES(701, 'item_priority', 'string', 'Priority of item to add to shopping list', false);
INSERT INTO config.tools_parameters(tool_id, param_name, param_type, param_description, is_required) VALUES(702, 'item_name', 'string', 'Name of item to find in shopping list', true);
INSERT INTO config.tools_parameters(tool_id, param_name, param_type, param_description, is_required) VALUES(704, 'item_name', 'string', 'Name of item to delete from shopping list', true);
