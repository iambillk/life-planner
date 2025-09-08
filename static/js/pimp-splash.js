// PIMP Splash Screen - First App Load Only
(function() {
    const hasSeenPIMP = sessionStorage.getItem('pimpSessionActive');
    
    if (!hasSeenPIMP) {
        // Array of loading messages - THE FULL PIMP EXPERIENCE!
        const pimpSayings = [
            // The professional ones
            "Organizing the hustle...",
            "Polishing the Cadillac...",
            "Counting the gold chains...",
            "Adjusting the peacock feather...",
            "Warming up the platform shoes...",
            "Activating purple velvet mode...",
            "Calibrating the pimp cane...",
            "Loading the bling...",
            "Preparing your empire...",
            "Shining the gold rings...",
            "Ironing the purple suit...",
            "Waxing the Coupe DeVille...",
            
            // The SPICY ones 😈
            "Slapping the bitches into line...",
            "Getting the hoes ready...",
            "Collecting the money from the honeys...",
            "Pimpin' ain't easy, loading ain't either...",
            "Powdering the pimp hand...",
            "Teaching these hoes about productivity...",
            "Organizing the stable...",
            "Getting the bitches their schedules...",
            "Counting last night's earnings...",
            "Waking up the bottom bitch...",
            "Distributing the daily quotas...",
            "Checking which hoe made the most...",
            "Keeping the pimp hand strong...",
            "Making sure these bitches know the plan...",
            "Getting ready to run this shit...",
            
            // Mix of both vibes
            "Stacking paper and slapping haters...",
            "Boss shit loading...",
            "Big PIMP energy initializing...",
            "Loading that playa shit...",
            "Getting this bread organized...",
            "Ain't no half-steppin', full PIMP loading..."
            
        ];
        
        // Pick a random saying
        const randomSaying = pimpSayings[Math.floor(Math.random() * pimpSayings.length)];
        
        // Create the splash screen with the random saying
        const splashHTML = `
            <div id="pimp-splash" style="
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: linear-gradient(135deg, #6B46C1 0%, #9333EA 50%, #FFD700 100%);
                z-index: 99999;
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                animation: pimpFadeIn 0.5s ease-out;
            ">
                <img src="/static/images/pimp.jpg" alt="PIMP - Personal Intelligence Management Platform" style="
                    max-width: 90%;
                    max-height: 70vh;
                    object-fit: contain;
                    animation: pimpEntrance 0.8s ease-out;
                    filter: drop-shadow(0 10px 30px rgba(0,0,0,0.5));
                ">
                <div style="
                    width: 300px;
                    height: 6px;
                    background: rgba(255, 255, 255, 0.2);
                    border-radius: 3px;
                    margin-top: 30px;
                    overflow: hidden;
                ">
                    <div id="pimp-progress" style="
                        height: 100%;
                        width: 0%;
                        background: linear-gradient(90deg, #FFD700, #FFA500);
                        border-radius: 3px;
                        transition: width 4.5s ease-out;
                    "></div>
                </div>
                <p style="
                    color: #FFD700;
                    font-family: 'Arial Black', sans-serif;
                    font-size: 1.4rem;
                    margin-top: 20px;
                    text-shadow: 2px 2px 4px rgba(0,0,0,0.5);
                    animation: pimpPulse 1s infinite;
                ">${randomSaying}</p>
            </div>
            
            <style>
                @keyframes pimpFadeIn {
                    from { opacity: 0; }
                    to { opacity: 1; }
                }
                
                @keyframes pimpEntrance {
                    from {
                        transform: scale(0.5) rotate(-10deg);
                        opacity: 0;
                    }
                    to {
                        transform: scale(1) rotate(0);
                        opacity: 1;
                    }
                }
                
                @keyframes pimpPulse {
                    0%, 100% { opacity: 1; transform: scale(1); }
                    50% { opacity: 0.8; transform: scale(0.98); }
                }
                
                @keyframes pimpFadeOut {
                    from { opacity: 1; }
                    to { opacity: 0; transform: scale(1.1); }
                }
            </style>
        `;
        
        // Insert splash screen
        document.body.insertAdjacentHTML('beforeend', splashHTML);
        
        // Start progress bar
        setTimeout(() => {
            const progress = document.getElementById('pimp-progress');
            if (progress) {
                progress.style.width = '100%';
            }
        }, 100);
        
        // Remove splash after 5 seconds
        setTimeout(() => {
            const splash = document.getElementById('pimp-splash');
            if (splash) {
                splash.style.animation = 'pimpFadeOut 0.5s ease-out forwards';
                setTimeout(() => {
                    splash.remove();
                    sessionStorage.setItem('pimpSessionActive', 'true');
                }, 500);
            }
        }, 5000);
    }
})();