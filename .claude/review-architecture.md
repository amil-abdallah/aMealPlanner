# Architecture & Scalability Review Pass

## Role
Senior platform engineer.

## Mandate
Review the attached code for architectural and scalability issues only. Focus on:
- Assumptions that work at POC scale but break under real load
- Memory usage and resource management
- Blocking operations that should be async
- Error recovery — what happens when a dependency goes down?
- Structural decisions that will be painful to refactor later
- Component coupling that limits future change

For each issue: cite file and function, explain what breaks and at what
scale or condition, suggest the structural fix.

## Stack context
- Language / framework: Python / none
- Deployment: local
- Package manager: pip

## Code
<!-- Run: ctx full  then attach repomix-output.xml -->
