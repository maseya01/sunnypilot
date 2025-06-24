/**
 * Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.
 *
 * This file is part of sunnypilot and is licensed under the MIT License.
 * See the LICENSE.md file in the root directory for more details.
 */

#include "selfdrive/ui/sunnypilot/qt/onroad/hud.h"

HudRendererSP::HudRendererSP() {}

void HudRendererSP::updateState(const UIState &s) {
  HudRenderer::updateState(s);

  // Extract lead vehicle distance from radarState
  const SubMaster &sm = *(s.sm);
  lead_distance_feet = -1.0f;
  if (sm.rcv_frame("radarState") >= s.scene.started_frame) {
    const auto &lead_one = sm["radarState"].getRadarState().getLeadOne();
    if (lead_one.getStatus()) {
      // dRel is in meters, convert to feet
      lead_distance_feet = lead_one.getDRel() * 3.28084f;
    }
  }
}

void HudRendererSP::draw(QPainter &p, const QRect &surface_rect) {
  // Always show set speed box, even if cruise is not available
  drawSetSpeed(p, surface_rect);
  drawCurrentSpeed(p, surface_rect);
  drawLeadDistance(p, surface_rect);
}

void HudRendererSP::drawLeadDistance(QPainter &p, const QRect &surface_rect) {
  if (lead_distance_feet > 0) {
    // Draw below the set speed box
    const QSize default_size = {172, 204};
    QRect set_speed_rect(QPoint(60, 45), default_size);
    int y = set_speed_rect.bottom() + 40;
    p.setFont(InterFont(40, QFont::Bold));
    p.setPen(QColor(255, 255, 255));
    QString text = QString::number(static_cast<int>(lead_distance_feet)) + " ft";
    p.drawText(set_speed_rect.x(), y, set_speed_rect.width(), 50, Qt::AlignHCenter | Qt::AlignTop, text);
  }
}
