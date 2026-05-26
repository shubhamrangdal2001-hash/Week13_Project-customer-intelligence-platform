#!/bin/sh
# Add Azure App Service internal hostname to /etc/hosts so the container can resolve its own public URL
if [ -n "$WEBSITE_HOSTNAME" ]; then
  echo "127.0.0.1 $WEBSITE_HOSTNAME" >> /etc/hosts
fi
# Start Streamlit
exec streamlit run app.py --server.port $PORT --server.address 0.0.0.0
