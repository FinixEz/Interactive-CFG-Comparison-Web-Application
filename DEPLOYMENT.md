# Deployment Guide

This guide will help you deploy the Interactive CFG Comparison Web Application to various cloud platforms.

## 🚀 Quick Deploy Options

### Option 1: Render (Recommended - Free Tier Available)

**Render** is the easiest option with a generous free tier.

#### Steps:

1. **Sign up for Render**
   - Go to [https://render.com](https://render.com)
   - Sign up with your GitHub account

2. **Create New Web Service**
   - Click "New +" → "Web Service"
   - Connect your GitHub repository: `https://github.com/FinixEz/Interactive-CFG-Comparison-Web-Application`
   - Render will automatically detect the `render.yaml` configuration

3. **Configure the Service** (if not auto-detected)
   - **Name**: `cfg-comparison-app` (or your choice)
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements-production.txt`
   - **Start Command**: `gunicorn --chdir webapp app:app --timeout 120 --workers 2 --bind 0.0.0.0:$PORT`
   - **Instance Type**: Free

4. **Set Environment Variables** (Optional but recommended)
   - Go to "Environment" tab
   - Add: `SECRET_KEY` = (generate a random string)
   - Add: `FLASK_ENV` = `production`

5. **Deploy**
   - Click "Create Web Service"
   - Wait 5-10 minutes for deployment
   - Your app will be live at: `https://your-app-name.onrender.com`

#### Free Tier Limitations:
- App may sleep after 15 minutes of inactivity (takes ~30 seconds to wake up)
- 750 hours/month of runtime
- Shared CPU/RAM

---

### Option 2: Railway (Free Tier Available)

**Railway** offers $5 free credit per month.

#### Steps:

1. **Sign up for Railway**
   - Go to [https://railway.app](https://railway.app)
   - Sign up with GitHub

2. **Create New Project**
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Choose your repository

3. **Configure**
   - Railway will auto-detect Python
   - Set environment variables:
     - `PORT` = `8080` (Railway provides this automatically)
     - `SECRET_KEY` = (random string)
     - `FLASK_ENV` = `production`

4. **Deploy**
   - Railway will automatically deploy
   - Get your URL from the "Settings" tab

---

### Option 3: PythonAnywhere (Free Tier Available)

**PythonAnywhere** is great for Python apps with a permanent free tier.

#### Steps:

1. **Sign up**
   - Go to [https://www.pythonanywhere.com](https://www.pythonanywhere.com)
   - Create a free account

2. **Clone Repository**
   - Open a Bash console
   ```bash
   git clone https://github.com/FinixEz/Interactive-CFG-Comparison-Web-Application.git
   cd Interactive-CFG-Comparison-Web-Application
   ```

3. **Create Virtual Environment**
   ```bash
   mkvirtualenv --python=/usr/bin/python3.10 cfgapp
   pip install -r requirements-production.txt
   ```

4. **Configure Web App**
   - Go to "Web" tab → "Add a new web app"
   - Choose "Manual configuration" → Python 3.10
   - Set source code directory: `/home/yourusername/Interactive-CFG-Comparison-Web-Application`
   - Set working directory: `/home/yourusername/Interactive-CFG-Comparison-Web-Application/webapp`

5. **Edit WSGI Configuration**
   - Click on WSGI configuration file
   - Replace contents with:
   ```python
   import sys
   import os
   
   # Add your project directory to the sys.path
   project_home = '/home/yourusername/Interactive-CFG-Comparison-Web-Application'
   if project_home not in sys.path:
       sys.path.insert(0, project_home)
   
   # Change to webapp directory
   os.chdir(os.path.join(project_home, 'webapp'))
   
   # Import the Flask app
   from app import app as application
   ```

6. **Set Environment Variables**
   - In the "Web" tab, scroll to "Environment variables"
   - Add `SECRET_KEY` with a random value

7. **Reload**
   - Click "Reload" button
   - Visit: `https://yourusername.pythonanywhere.com`

#### Free Tier Limitations:
- Limited CPU time per day
- No custom domains
- App must be reloaded every 3 months

---

### Option 4: Heroku (Paid - $5/month minimum)

**Note**: Heroku no longer has a free tier, but it's still popular.

#### Steps:

1. **Install Heroku CLI**
   ```bash
   curl https://cli-assets.heroku.com/install.sh | sh
   ```

2. **Login**
   ```bash
   heroku login
   ```

3. **Create App**
   ```bash
   cd /home/finix/Documents/Project
   heroku create your-app-name
   ```

4. **Set Environment Variables**
   ```bash
   heroku config:set SECRET_KEY=$(python -c 'import secrets; print(secrets.token_hex(32))')
   heroku config:set FLASK_ENV=production
   ```

5. **Deploy**
   ```bash
   git push heroku master
   ```

6. **Open App**
   ```bash
   heroku open
   ```

---

## 🔧 Environment Variables

For production deployment, set these environment variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `SECRET_KEY` | Flask secret key for sessions | `your-random-secret-key-here` |
| `FLASK_ENV` | Environment mode | `production` |
| `PORT` | Port to run on (usually auto-set) | `8080` |
| `UPLOAD_FOLDER` | Upload directory | `uploads` |

### Generate a Secret Key:
```bash
python -c 'import secrets; print(secrets.token_hex(32))'
```

---

## 📊 Post-Deployment Checklist

After deploying, verify:

- ✅ Home page loads correctly
- ✅ Sample data works on comparison page
- ✅ Sample data works on inspector page
- ✅ File upload works (test with small files first)
- ✅ CFG visualization renders properly
- ✅ No errors in application logs

---

## 🐛 Troubleshooting

### Issue: App crashes on startup
**Solution**: Check logs for missing dependencies or Python version mismatch

### Issue: File uploads fail
**Solution**: 
- Ensure upload directory has write permissions
- Check file size limits (default 16MB)
- Verify disk space on deployment platform

### Issue: CFG generation times out
**Solution**: 
- Increase timeout in Procfile (currently 120 seconds)
- Consider upgrading to paid tier for more resources
- Optimize large assembly files before upload

### Issue: Static files not loading
**Solution**: 
- Ensure `static/` directory is included in deployment
- Check that paths are relative, not absolute
- Verify web server is serving static files correctly

---

## 🔒 Security Recommendations

1. **Always set a strong SECRET_KEY** in production
2. **Use HTTPS** (most platforms provide this automatically)
3. **Set `FLASK_ENV=production`** to disable debug mode
4. **Monitor file uploads** for malicious content
5. **Set up rate limiting** if expecting high traffic
6. **Regular updates** - keep dependencies up to date

---

## 📈 Scaling Considerations

If your app gets popular:

1. **Upgrade to paid tier** for better performance
2. **Add caching** (Redis/Memcached) for graph comparisons
3. **Use CDN** for static assets
4. **Implement job queue** (Celery) for long-running CFG generation
5. **Database** - Store processed graphs instead of regenerating
6. **Load balancing** - Multiple worker instances

---

## 💰 Cost Comparison

| Platform | Free Tier | Paid Tier | Best For |
|----------|-----------|-----------|----------|
| **Render** | ✅ 750hrs/month | $7/month | Easy deployment |
| **Railway** | ✅ $5 credit/month | $5+/month | Modern interface |
| **PythonAnywhere** | ✅ Limited CPU | $5/month | Python-specific |
| **Heroku** | ❌ None | $5+/month | Enterprise features |
| **DigitalOcean** | ❌ None | $4+/month | Full control |

---

## 🎯 Recommended Choice

**For this project, I recommend Render** because:
- ✅ Free tier is generous
- ✅ Automatic deployments from GitHub
- ✅ Easy configuration with `render.yaml`
- ✅ Good performance for Flask apps
- ✅ HTTPS included
- ✅ No credit card required for free tier

---

## 📞 Need Help?

If you encounter issues:
1. Check the platform's documentation
2. Review application logs
3. Test locally first with `gunicorn --chdir webapp app:app`
4. Open an issue on GitHub

---

**Ready to deploy? Start with Render for the easiest experience!**
