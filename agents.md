# The ShowSphere web app

## Business Requirements

This project is building a Exhibitor Services Agent Platform "ShowSphere" which will be a collection of agents,assisting various business processes related to Trade
Show Planning , Servicing and Execution. All these agents will continue to work on a common and evolving symantic layer which would be on a neo4j graph database.

### Key Features

##### Should have a login Page
##### Should be able to create a New Agent or Open existing Agent
##### For every Agent there will be a setup page, to choose the model between Claude or Open ai, Select data source, build Ontology layer

#### The live ontology layer will be visible in every agent interaction and for every prompt fired via the chat interface to the aegnt, the ontology layer traversal needs to be highlighted through animation.

##### Ontology Creation agent will have its own configuration and will have inbuilt Research , Analysis, Reasoning & Evaluation capbilities , in order
to create a comprehensive graph data model , based on the ingested dataset
##### Every newly ingested data point will get integrated with the Ontology layer, thereby evolving the ontology layer, for better agent context
##### For every Agent, there will be a chat interface to interact and also there will be a canvas board for the agent to dynamically generate and create outputs like interactive
maps, dashboards, bar charts, graphs. All this will be based on user prompt and corresponding agent output


## Limitations

For the MVP, there will only be a user sign in (hardcoded to 'user' and 'password') but the database will support multiple users for future.

For the MVP, this will run locally (in a docker container)

## Technical Decisions

- NextJS frontend
- Python FastAPI backend; Next.js runs as a separate Node process, FastAPI serves the API at /api
- Two separate Docker containers (frontend + backend) managed by docker compose
- Use "uv" as the package manager for python in the Docker container
- Use SQLLite local database for the database, creating a new db if it doesn't exist
- Use Neo4j Database for building of Semantic layer/ontology layer
- Start and Stop server scripts for Mac, PC, Linux in scripts/


## Color Scheme

-Coral Primary: #FF7A59 - main CTA buttons, key actions, brand accent
-Pickled Bluewood: #33475B - main headings, navigation background, logo
-Deep Bluewood: #2D3E50 - sidebar, nav background, dark surfaces
-Cerulean: #0091AE - links, interactive elements, info states
-Jade: #00BDA5 - success states, Closed Won stage, positive indicators
-Marigold: #F5C26B - warnings, alerts, Proposal stage highlight
-Watermelon: #F2545B - errors, danger states, Closed Lost stage
-Slate: #516F90 - muted text, secondary labels, supporting copy
-Heather: #7C98B6 - placeholder text, hints, inactive elements
-Fog: #EAF0F6 - page backgrounds, table row fills
-Geyser: #DFE3EB - borders, dividers, card outlines
-Forget Me Not: #FFF1EE - coral tint background, hero sections, empty states

## Fonts and Themes
-Use Enterprise theme

## Coding standards

1. Use latest versions of libraries and idiomatic approaches as of today
2. Keep it simple - NEVER over-engineer, ALWAYS simplify, NO unnecessary defensive programming. No extra features - focus on simplicity.
3. Be concise. Keep README minimal. IMPORTANT: no emojis ever
4. When hitting issues, always identify root cause before trying a fix. Do not guess. Prove with evidence, then fix the root cause.

## Working documentation

All documents for planning and executing this project will be in the docs/ directory.
Please review the docs/PLAN.md document before proceeding.

---