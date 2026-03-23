clc; clear; close all;
%% ── CONSTANTS ─────────────────────────────────────────────────────────────
PUNCH_MASS = 0.8;   % kg
%% ── 1. LOAD DATA ──────────────────────────────────────────────────────────
scriptDir  = fileparts(mfilename('fullpath'));
dataFolder = fullfile(scriptDir, 'PunchData');   % <-- rename if needed
csvFiles = dir(fullfile(dataFolder, '*.csv'));
nPunches = numel(csvFiles);
if nPunches == 0
   error('No CSV files found in:\n  %s\nCheck "dataFolder" points to the right folder.', dataFolder);
end
for k = 1:nPunches
   T = readtable(fullfile(dataFolder, csvFiles(k).name));
   aMag      = sqrt(T.ax.^2 + T.ay.^2 + T.az.^2) * 9.81;
   triggered = T.fsr_raw > 0;
   force     = PUNCH_MASS .* aMag .* triggered;
   punches(k).name     = csvFiles(k).name;
   punches(k).t        = T.t_ms;
   punches(k).ax       = T.ax;
   punches(k).ay       = T.ay;
   punches(k).az       = T.az;
   punches(k).gx       = T.gx;
   punches(k).gy       = T.gy;
   punches(k).gz       = T.gz;
   punches(k).fsr_raw  = T.fsr_raw;
   punches(k).fsr_v    = T.fsr_v;
   punches(k).force    = force;
   punches(k).maxForce = max(force);
end
fprintf('Loaded %d punch files.\n', nPunches);
%% ── 2. COLOUR PALETTE (dark-mode) ─────────────────────────────────────────
palette = [
   0.00  0.80  1.00
   1.00  0.41  0.16
   0.18  1.00  0.44
   1.00  0.20  0.60
   0.94  0.90  0.10
   0.62  0.35  1.00
   0.10  0.85  0.85
   1.00  0.65  0.00
   0.55  1.00  0.20
];
bgCol = [0.12 0.12 0.12];
axCol = [0.88 0.88 0.88];
%% ── 3. MAX FORCE OVERVIEW ─────────────────────────────────────────────────
maxForces = [punches.maxForce];
figMax = figure('Name','Max Force per Punch  –  click a dot to inspect', ...
               'Color',bgCol,'Position',[220 200 820 380]);
axMax  = axes('Parent',figMax,'Color',bgCol, ...
             'XColor',axCol,'YColor',axCol, ...
             'GridColor',[0.35 0.35 0.35],'GridAlpha',0.6);
hold(axMax,'on'); grid(axMax,'on');
stem(axMax, 1:nPunches, maxForces, ...
    'Color',[0.40 0.40 0.40],'LineWidth',1,'Marker','none');
for k = 1:nPunches
   scatter(axMax, k, maxForces(k), 140, palette(k,:), ...
           'filled','MarkerEdgeColor','w','LineWidth',0.8);
end
xlabel(axMax,'Punch #',        'Color',axCol,'FontSize',11);
ylabel(axMax,'Peak Force (N)', 'Color',axCol,'FontSize',11);
title(axMax,  'Peak Punch Force  –  click any dot to open detail plots', ...
     'Color',axCol,'FontSize',13,'FontWeight','bold');
xlim(axMax,[0.5, nPunches+0.5]);  xticks(axMax,1:nPunches);
dcm = datacursormode(figMax);
set(dcm,'UpdateFcn',@(~,evt) dataTipLabel(evt,punches));
set(figMax,'WindowButtonDownFcn', ...
   @(src,~) onMaxForceFigClick(src,axMax,punches,palette,bgCol,axCol));
fprintf('Ready — click any dot to open the 3 linked detail plots.\n');
%% ══════════════════════════════════════════════════════════════════════════
%  LOCAL FUNCTIONS
%% ══════════════════════════════════════════════════════════════════════════
function onMaxForceFigClick(~, axMax, punches, palette, bgCol, axCol)
   cp     = get(axMax,'CurrentPoint');
   xClick = cp(1,1);
   nP     = numel(punches);
   if xClick < 0.5 || xClick > nP+0.5; return; end
   k = max(1, min(round(xClick), nP));
   openDetailPlots(k, punches, palette, bgCol, axCol);
end
% ─────────────────────────────────────────────────────────────────────────
function openDetailPlots(k, punches, palette, bgCol, axCol)
   p   = punches(k);
   col = palette(k,:);
   N   = numel(p.t);
   %% ── Figure layout ────────────────────────────────────────────────────
   W=640; H=560; gap=24; x0=30; y0=50;
   figA = figure('Name',sprintf('Punch %d – Acceleration 3D Comet',k), ...
                 'Color',bgCol,'Position',[x0,            y0, W, H]);
   figG = figure('Name',sprintf('Punch %d – Gyroscope 3D Comet',k), ...
                 'Color',bgCol,'Position',[x0+W+gap,      y0, W, H]);
   figF = figure('Name',sprintf('Punch %d – Calculated Force',k), ...
                 'Color',bgCol,'Position',[x0+2*(W+gap),  y0, W, H]);
   %% ── Axes (leave room at bottom for slider + button) ──────────────────
   % Axes occupy top ~78% of each figure; bottom strip holds controls
   axPos = [0.10 0.22 0.85 0.70];   % [left bottom width height] normalised
   axA = axes('Parent',figA,'Color',bgCol,'Position',axPos, ...
              'XColor',axCol,'YColor',axCol,'ZColor',axCol, ...
              'GridColor',[0.35 0.35 0.35],'GridAlpha',0.6);
   hold(axA,'on'); grid(axA,'on'); view(axA,35,25);
   axG = axes('Parent',figG,'Color',bgCol,'Position',axPos, ...
              'XColor',axCol,'YColor',axCol,'ZColor',axCol, ...
              'GridColor',[0.35 0.35 0.35],'GridAlpha',0.6);
   hold(axG,'on'); grid(axG,'on'); view(axG,35,25);
   axF = axes('Parent',figF,'Color',bgCol,'Position',axPos, ...
              'XColor',axCol,'YColor',axCol, ...
              'GridColor',[0.35 0.35 0.35],'GridAlpha',0.6);
   hold(axF,'on'); grid(axF,'on');
   %% ── Axis labels / titles ─────────────────────────────────────────────
   xlabel(axA,'ax (g)','Color',axCol,'FontSize',10);
   ylabel(axA,'ay (g)','Color',axCol,'FontSize',10);
   zlabel(axA,'az (g)','Color',axCol,'FontSize',10);
   title(axA,sprintf('Punch %d – Acceleration 3D Comet',k), ...
         'Color',axCol,'FontSize',12,'FontWeight','bold');
   xlabel(axG,'gx (°/s)','Color',axCol,'FontSize',10);
   ylabel(axG,'gy (°/s)','Color',axCol,'FontSize',10);
   zlabel(axG,'gz (°/s)','Color',axCol,'FontSize',10);
   title(axG,sprintf('Punch %d – Gyroscope 3D Comet',k), ...
         'Color',axCol,'FontSize',12,'FontWeight','bold');
   xlabel(axF,'Time (ms)','Color',axCol,'FontSize',10);
   ylabel(axF,'Force (N)', 'Color',axCol,'FontSize',10);
   title(axF,sprintf('Punch %d – Calculated Force  (F = m·|a|,  m = 0.8 kg)',k), ...
         'Color',axCol,'FontSize',12,'FontWeight','bold');
   %% ── Ghost traces ─────────────────────────────────────────────────────
   dimCol = col*0.30 + bgCol*0.70;
   plot3(axA, p.ax, p.ay, p.az, '-','Color',[dimCol 0.35],'LineWidth',0.7);
   plot3(axG, p.gx, p.gy, p.gz, '-','Color',[dimCol 0.35],'LineWidth',0.7);
   plot(axF,  p.t,  p.force,    '-','Color',[dimCol 0.45],'LineWidth',0.7);
   % Peak force marker on force plot
   [pk,pkI] = max(p.force);
   scatter(axF, p.t(pkI), pk, 160,'w','p','filled', ...
           'MarkerEdgeColor',col,'LineWidth',1.5);
   text(axF, p.t(pkI), pk, sprintf('  %.1f N',pk), ...
        'Color','w','FontSize',9,'VerticalAlignment','bottom');
   %% ── Animated comet handles ───────────────────────────────────────────
   bodyLen  = max(2, floor(0.12*N));
   bodyFrac = max(1, floor(bodyLen/3));
   dimC     = col*0.50 + 0.10;
   hA_tail = plot3(axA,p.ax(1),p.ay(1),p.az(1),'-','Color',dimC,'LineWidth',1.0);
   hA_body = plot3(axA,p.ax(1),p.ay(1),p.az(1),'-','Color',col, 'LineWidth',2.2);
   hA_head = plot3(axA,p.ax(1),p.ay(1),p.az(1),'o','Color','w', ...
                   'MarkerFaceColor',col,'MarkerSize',9);
   hG_tail = plot3(axG,p.gx(1),p.gy(1),p.gz(1),'-','Color',dimC,'LineWidth',1.0);
   hG_body = plot3(axG,p.gx(1),p.gy(1),p.gz(1),'-','Color',col, 'LineWidth',2.2);
   hG_head = plot3(axG,p.gx(1),p.gy(1),p.gz(1),'o','Color','w', ...
                   'MarkerFaceColor',col,'MarkerSize',9);
   hF_tail = plot(axF,p.t(1),p.force(1),'-','Color',dimC,'LineWidth',1.0);
   hF_body = plot(axF,p.t(1),p.force(1),'-','Color',col, 'LineWidth',2.2);
   hF_head = plot(axF,p.t(1),p.force(1),'o','Color','w', ...
                  'MarkerFaceColor',col,'MarkerSize',9);
   %% ── Live value readout text handles ──────────────────────────────────
   % Placed in the top-left of each axes using annotation-style text
   valA = text(axA, 0,0,0, '', 'Color','w','FontSize',9, ...
               'Units','normalized','Position',[0.02 0.97 0], ...
               'VerticalAlignment','top','FontName','Courier New');
   valG = text(axG, 0,0,0, '', 'Color','w','FontSize',9, ...
               'Units','normalized','Position',[0.02 0.97 0], ...
               'VerticalAlignment','top','FontName','Courier New');
   valF = text(axF, 0,0,   '', 'Color','w','FontSize',9, ...
               'Units','normalized','Position',[0.02 0.97], ...
               'VerticalAlignment','top','FontName','Courier New');
   % Vertical time-cursor line on force plot
   hVline = xline(axF, p.t(1), '--', 'Color',[1 1 1 0.5], 'LineWidth',1.2);
   %% ── Controls: slider + pause button ─────────────────────────────────
   % Slider spans most of the bottom strip; button sits to the right
   % Positions in pixels [left bottom width height]
   slW = W-160;  slH = 22;  slX = 15;   slY = 52;
   btW = 115;    btH = 34;  btX = W-135; btY = 44;
   sliderStyle = {'Style','slider','Min',1,'Max',N,'Value',1, ...
                  'SliderStep',[1/(N-1), 10/(N-1)], ...
                  'BackgroundColor',[0.25 0.25 0.25], ...
                  'Position',[slX slY slW slH]};
   sldA = uicontrol(figA, sliderStyle{:});
   sldG = uicontrol(figG, sliderStyle{:});
   sldF = uicontrol(figF, sliderStyle{:});
   % Slider time label (shows current ms)
   lblStyle = {'Style','text','BackgroundColor',bgCol,'ForegroundColor',axCol, ...
               'FontSize',9,'HorizontalAlignment','left'};
   lblA = uicontrol(figA, lblStyle{:}, 'Position',[slX slY+slH+2 160 16], ...
                    'String',sprintf('t = %d ms', round(p.t(1))));
   lblG = uicontrol(figG, lblStyle{:}, 'Position',[slX slY+slH+2 160 16], ...
                    'String',sprintf('t = %d ms', round(p.t(1))));
   lblF = uicontrol(figF, lblStyle{:}, 'Position',[slX slY+slH+2 160 16], ...
                    'String',sprintf('t = %d ms', round(p.t(1))));
   btnStyle = {'Style','pushbutton', ...
               'BackgroundColor',[0.22 0.22 0.22],'ForegroundColor','w', ...
               'FontSize',11,'FontWeight','bold','String','⏸  Pause', ...
               'Position',[btX btY btW btH]};
   btnA = uicontrol(figA, btnStyle{:});
   btnG = uicontrol(figG, btnStyle{:});
   btnF = uicontrol(figF, btnStyle{:});
   allFigs  = [figA,  figG,  figF ];
   allBtns  = [btnA,  btnG,  btnF ];
   allSlds  = [sldA,  sldG,  sldF ];
   allLbls  = [lblA,  lblG,  lblF ];
   %% ── Shared state in figA UserData ────────────────────────────────────
   st.paused      = false;
   st.scrubIdx    = 1;          % index set by slider (0 = not scrubbing)
   st.sliderMoved = false;
   for f = allFigs; set(f,'UserData',st); end
   %% ── Callbacks ────────────────────────────────────────────────────────
   pauseCb  = @(~,~) togglePause(allFigs, allBtns);
   set(btnA,'Callback',pauseCb);
   set(btnG,'Callback',pauseCb);
   set(btnF,'Callback',pauseCb);
   % Slider callback: pause animation and jump all plots to chosen frame
   sliderCb = @(src,~) onSlider(src, allFigs, allSlds, allLbls, p, ...
                                 hA_tail,hA_body,hA_head, ...
                                 hG_tail,hG_body,hG_head, ...
                                 hF_tail,hF_body,hF_head, ...
                                 hVline, valA,valG,valF, ...
                                 bodyLen,bodyFrac,allBtns);
   set(sldA,'Callback',sliderCb);
   set(sldG,'Callback',sliderCb);
   set(sldF,'Callback',sliderCb);
   %% ── Animation loop ───────────────────────────────────────────────────
   % 2× slower: halve stepSize vs previous (target ~110 logical steps)
   stepSize = max(1, floor(N/110));
   i = 1;
   while ishandle(figA) && ishandle(figG) && ishandle(figF)
       if ~isvalid(hA_head) || ~isvalid(hG_head) || ~isvalid(hF_head)
           break;
       end
       st = get(figA,'UserData');
       % If slider was moved, sync animation index to slider position
       if st.sliderMoved
           i = st.scrubIdx;
           st.sliderMoved = false;
           for f = allFigs; set(f,'UserData',st); end
       end
       if st.paused
           pause(0.04);
           continue;
       end
       if i > N; i = 1; end
       % Update all three plots and readouts
       updateFrame(i, p, bodyLen, bodyFrac, ...
                   hA_tail,hA_body,hA_head, ...
                   hG_tail,hG_body,hG_head, ...
                   hF_tail,hF_body,hF_head, ...
                   hVline, valA,valG,valF);
       % Sync sliders and labels to animation position
       sliderVal = max(1, min(N, i));
       for s = allSlds
           if ishandle(s); set(s,'Value',sliderVal); end
       end
       tNow = round(p.t(i));
       for l = allLbls
           if ishandle(l); set(l,'String',sprintf('t = %d ms',tNow)); end
       end
       i = i + stepSize;
       drawnow limitrate;
   end
end
% ─────────────────────────────────────────────────────────────────────────
function updateFrame(i, p, bodyLen, bodyFrac, ...
                    hA_tail,hA_body,hA_head, ...
                    hG_tail,hG_body,hG_head, ...
                    hF_tail,hF_body,hF_head, ...
                    hVline, valA,valG,valF)
   % Update comet geometry and readout text for index i
   t0 = max(1, i - bodyLen);
   t1 = max(1, i - bodyFrac);
   set(hA_tail,'XData',p.ax(t0:i),'YData',p.ay(t0:i),'ZData',p.az(t0:i));
   set(hA_body,'XData',p.ax(t1:i),'YData',p.ay(t1:i),'ZData',p.az(t1:i));
   set(hA_head,'XData',p.ax(i),   'YData',p.ay(i),   'ZData',p.az(i));
   set(hG_tail,'XData',p.gx(t0:i),'YData',p.gy(t0:i),'ZData',p.gz(t0:i));
   set(hG_body,'XData',p.gx(t1:i),'YData',p.gy(t1:i),'ZData',p.gz(t1:i));
   set(hG_head,'XData',p.gx(i),   'YData',p.gy(i),   'ZData',p.gz(i));
   set(hF_tail,'XData',p.t(t0:i),'YData',p.force(t0:i));
   set(hF_body,'XData',p.t(t1:i),'YData',p.force(t1:i));
   set(hF_head,'XData',p.t(i),    'YData',p.force(i));
   % Vertical cursor on force plot
   set(hVline,'Value',p.t(i));
   % Live value readouts
   set(valA,'String', sprintf('ax=%.2fg  ay=%.2fg  az=%.2fg', ...
       p.ax(i), p.ay(i), p.az(i)));
   set(valG,'String', sprintf('gx=%.1f  gy=%.1f  gz=%.1f °/s', ...
       p.gx(i), p.gy(i), p.gz(i)));
   set(valF,'String', sprintf('F = %.1f N', p.force(i)));
end
% ─────────────────────────────────────────────────────────────────────────
function onSlider(src, allFigs, allSlds, allLbls, p, ...
                 hA_tail,hA_body,hA_head, ...
                 hG_tail,hG_body,hG_head, ...
                 hF_tail,hF_body,hF_head, ...
                 hVline, valA,valG,valF, ...
                 bodyLen, bodyFrac, allBtns)
   % Pause animation, sync all sliders, and render the chosen frame
   i = max(1, min(numel(p.t), round(get(src,'Value'))));
   % Pause all
   st = get(allFigs(1),'UserData');
   if ~st.paused
       st.paused = true;
       for f = allFigs; if ishandle(f); set(f,'UserData',st); end; end
       for b = allBtns; if ishandle(b); set(b,'String','▶  Play'); end; end
   end
   % Sync slider positions and time labels
   tNow = round(p.t(i));
   for s = allSlds
       if ishandle(s); set(s,'Value',i); end
   end
   for l = allLbls
       if ishandle(l); set(l,'String',sprintf('t = %d ms',tNow)); end
   end
   % Render frame
   updateFrame(i, p, bodyLen, bodyFrac, ...
               hA_tail,hA_body,hA_head, ...
               hG_tail,hG_body,hG_head, ...
               hF_tail,hF_body,hF_head, ...
               hVline, valA,valG,valF);
   % Tell animation loop to resume from this index when un-paused
   st.scrubIdx    = i;
   st.sliderMoved = true;
   for f = allFigs; if ishandle(f); set(f,'UserData',st); end; end
   drawnow;
end
% ─────────────────────────────────────────────────────────────────────────
function togglePause(allFigs, allBtns)
   st = get(allFigs(1),'UserData');
   st.paused = ~st.paused;
   newLabel  = '▶  Play';
   if ~st.paused; newLabel = '⏸  Pause'; end
   for f = allFigs; if ishandle(f); set(f,'UserData',st); end; end
   for b = allBtns; if ishandle(b); set(b,'String',newLabel); end; end
end
% ─────────────────────────────────────────────────────────────────────────
function txt = dataTipLabel(evt, punches)
   pos = get(evt,'Position');
   k   = max(1, min(round(pos(1)), numel(punches)));
   txt = { sprintf('Punch %d', k), ...
           sprintf('Peak Force: %.1f N', pos(2)), ...
           punches(k).name };
end

