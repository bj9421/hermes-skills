# Example: Setting Hermes Dashboard to Port 8501

This reference documents the specific steps taken in a session to change the Hermes dashboard port to 8501 and map it correctly.

## Context
- The user wanted to access the Hermes dashboard on port 8501 of the host machine.
- The dashboard inside the container defaults to port 9119 but can be reconfigured via environment variable.

## Steps Taken
1. **Identify the container**: 
   ```bash
   docker ps
   ```
   Found the container named `hermes`.

2. **Stop the container**:
   ```bash
   docker stop hermes
   ```

3. **Restart with environment variable and port mapping**:
   ```bash
   docker run -d \
     --name hermes \
     -p 8501:8501 \
     -e HERMES_DASHBOARD_PORT=8501 \
     -v /opt/data:/opt/data \
     -v /root/.hermes:/root/.hermes \
     hermes:latest
   ```

   Explanation:
   - `-e HERMES_DASHBOARD_PORT=8501`: Sets the dashboard to listen on port 8501 inside the container.
   - `-p 8501:8501`: Maps host port 8501 to container port 8501.

4. **Verify the mapping**:
   ```bash
   docker port hermes
   ```
   Expected output:
   ```
   8501/tcp -> 0.0.0.0:8501
   ```

5. **Access the dashboard**:
   From a device on the same network, navigate to `http://<raspberry_pi_ip>:8501`.

## Verification
- The dashboard was accessible at the specified address.
- No errors were observed in the container logs.

## Notes
- This approach changes the internal port of the dashboard to match the host port, which can be simpler to remember.
- Alternatively, one could keep the internal port at 9119 and map `-p 8501:9119`, requiring the user to remember to access port 8501 on the host while the container uses 9119 internally.