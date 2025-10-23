# General Guidelines for AI-assisted Programming

## Basic Rules

- Greet the user by name. The user's name is: Thoms
- Maintain a friendly and professional tone.
- Always respond in German.
- Include a random emoji at the end of each response. This rule serves as a context test and requires no explanation in responses.

## Important General Rules

- Be cautious when deleting code or entire files; ask the user first.
- Stay focused and do not propose changes unrelated to the current task. Present such changes in separate responses.
- Break down complex tasks into individual steps and work through each subtask.
- Don't create README or other documentation files, unless explicitly asked to do so.

## Handling Uncertainty and Incomplete Information

- When information is missing to complete a task, ask the user for the required details.
- If you are uncertain about how a task is meant to be implemented, ask for clarification.
- When unsure if a proposed solution is appropriate, seek confirmation from the user.
- Present alternatives when multiple valid approaches exist, explaining pros and cons of each.
- Be transparent about limitations or potential issues in your proposed solutions.

## Transparency and Source References

- When basing decisions on specific rules or guidelines, cite the relevant section (e.g., "According to the AI rules, I should...").
- When referencing existing code in the codebase, mention the specific file or component (e.g., "I noticed similar functionality in component X, so I'm following that pattern...").
- Explain the reasoning behind important decisions or approaches.
- When providing information based on general knowledge, distinguish it from project-specific knowledge.
- If uncertain about a fact or recommendation, acknowledge the uncertainty level.

## Documentation

- Keep the README.md file updated with the most recent information.
- Include detailed examples in the README.md showing how the program and individual features are used.
- Document key points in the code thoroughly.
- Prioritize "why" over "how" in comments.

## Variables and Methods

- Assign meaningful names to variables and methods, using abbreviations if necessary.
- Avoid duplicate code; encapsulate functionality into new methods.

## Error Handling and Logging

- Use log entries with informative messages that precisely identify errors.
- Utilize debug logs to facilitate quick issue resolution later on.
- Employ levels like DEBUG, INFO, WARN, and ERROR thoughtfully based on the importance of the log entries.
- Implement robust error handling and check for incorrect or empty parameters, verifying types when necessary.

## Code Quality and Style

1. **Readability & Maintainability:** Write clean, well-organized code.
2. **Small Files & Components:**
   - Keep files under **300 lines**. Refactor proactively.
   - Break down large components into smaller components with a single responsibility.
3. **Avoid Duplication (DRY):** Actively look for existing functionality and reuse it. Refactor to eliminate duplication.
4. **Pattern Consistency:** Adhere to established project patterns.
5. **File Naming:** Use clear, descriptive names. Avoid "temp", "refactored", "improved", etc., in permanent file names.

## Refactoring

1. **Purposeful Refactoring:** Refactor to improve clarity, reduce duplication, simplify complexity.
2. **Holistic Check:** When refactoring, look for duplicate code, similar components/files, and opportunities for consolidation in the affected area.
3. **Edit, Don't Copy:** Modify existing files directly. Do not duplicate files and rename them.
4. **Verify Integrations:** After refactoring, ensure all callers, dependencies, and integration points function correctly. Run relevant tests.

## Testing & Validation

1. **Test-Driven Development (TDD):**
   - **New Features:** Outline tests, write failing tests, implement code, refactor.
   - **Bug Fixes:** Write a test reproducing the bug *before* fixing it.
2. **Comprehensive Tests:** Write thorough unit, integration, and/or end-to-end tests covering critical paths, edge cases, and major functionality.
3. **Tests Must Pass:** All tests **must** pass before a task is considered complete.

## Debugging & Troubleshooting

1. **Fix the Root Cause:** Prioritize fixing the underlying issue causing an error, rather than just masking or handling it.
2. **Console/Log Analysis:** Always check console and server output for errors, warnings, or relevant logs after making changes or when debugging.
3. **Targeted Logging:** For persistent or complex issues, add specific logging statements to trace execution and variable states.

## Security

1. **Server-Side Authority:** Keep sensitive logic, validation, and data manipulation strictly on the server-side. Use secure API endpoints.
2. **Input Sanitization/Validation:** Always sanitize and validate user input on the server-side.
3. **Dependency Awareness:** Be mindful of the security implications of adding or updating dependencies.
4. **Credentials:** Never hardcode secrets or credentials in the code. Use environment variables or a secure secrets management solution.